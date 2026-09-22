//! Runtime-level planner, decision execution engine, backend registry, and domain service contracts.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, HashMap};
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;

use edge_decision::{
    DecisionBackend, DecisionInput, DecisionItemResult, DecisionStatus, EscalationPolicy,
    EscalationTarget,
};
use edge_kernel::{CapabilitySet, Context, EdgeError, EdgeResult};
use edge_search::{RankedCandidate, SearchQuery};

pub type RuntimeFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

#[derive(Default)]
pub struct DecisionBackendRegistry {
    backends: HashMap<String, Arc<dyn DecisionBackend>>,
    default_backend_id: String,
}

impl DecisionBackendRegistry {
    pub fn new() -> Self {
        Self {
            backends: HashMap::new(),
            default_backend_id: "deterministic".to_string(),
        }
    }

    pub fn register(&mut self, backend: Arc<dyn DecisionBackend>) {
        let name_str = backend.id().to_ascii_lowercase();
        self.backends.insert(name_str, backend);
    }

    pub fn register_with_name(&mut self, name: impl Into<String>, backend: Arc<dyn DecisionBackend>) {
        let name_str = name.into().to_ascii_lowercase();
        self.backends.insert(name_str, backend);
    }

    pub fn set_default_backend(&mut self, name: impl Into<String>) {
        self.default_backend_id = name.into().to_ascii_lowercase();
    }

    pub fn get(&self, name: &str) -> Option<Arc<dyn DecisionBackend>> {
        self.backends.get(&name.to_ascii_lowercase()).cloned()
    }

    pub fn resolve(&self, preferred_name: Option<&str>) -> EdgeResult<Arc<dyn DecisionBackend>> {
        let target_id = preferred_name
            .map(|s| s.to_ascii_lowercase())
            .unwrap_or_else(|| self.default_backend_id.clone());

        self.get(&target_id).ok_or_else(|| {
            EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::NotFound,
                format!("Decision backend '{}' is not registered", target_id),
            )
        })
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct RuntimeDecisionPolicy {
    pub minimum_escalation_threshold: f32,
}

impl Default for RuntimeDecisionPolicy {
    fn default() -> Self {
        Self {
            minimum_escalation_threshold: 0.50,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum DecisionRouteAction {
    Execute {
        result: DecisionItemResult,
        effective_threshold: f32,
    },
    Escalate {
        result: DecisionItemResult,
        effective_threshold: f32,
        target: EscalationTarget,
    },
}

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionBatchRouteResult {
    pub items: Vec<DecisionRouteAction>,
}

pub struct DecisionExecutionEngine {
    policy: RuntimeDecisionPolicy,
}

impl DecisionExecutionEngine {
    pub fn new(policy: RuntimeDecisionPolicy) -> Self {
        Self { policy }
    }

    pub fn evaluate(
        &self,
        backend: &dyn DecisionBackend,
        input: DecisionInput,
        policies: &HashMap<String, EscalationPolicy>,
    ) -> EdgeResult<DecisionBatchRouteResult> {
        let batch_result = backend.decide(input).map_err(|e| {
            EdgeError::new(edge_kernel::errors::EdgeErrorKind::Internal, e.message)
        })?;

        let mut items = Vec::with_capacity(batch_result.results.len());

        for item in batch_result.results {
            let policy = policies.get(&item.question_id);
            let domain_threshold = policy.map(|p| p.threshold).unwrap_or(0.0);
            let effective_threshold =
                domain_threshold.max(self.policy.minimum_escalation_threshold);
            let target = policy
                .map(|p| p.target)
                .unwrap_or(EscalationTarget::IntentModel);

            if item.status == DecisionStatus::Accepted && item.confidence >= effective_threshold {
                items.push(DecisionRouteAction::Execute {
                    result: item,
                    effective_threshold,
                });
            } else {
                items.push(DecisionRouteAction::Escalate {
                    result: item,
                    effective_threshold,
                    target,
                });
            }
        }

        Ok(DecisionBatchRouteResult { items })
    }

    pub fn evaluate_registered(
        &self,
        registry: &DecisionBackendRegistry,
        preferred_backend: Option<&str>,
        input: DecisionInput,
        policies: &HashMap<String, EscalationPolicy>,
    ) -> EdgeResult<DecisionBatchRouteResult> {
        let backend = registry.resolve(preferred_backend)?;
        self.evaluate(backend.as_ref(), input, policies)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct RecommendationRequest {
    pub constraints: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ResolveRequest {
    pub item_id: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ResolvedItem {
    pub item_id: String,
    pub title: String,
    pub uri: String,
    pub headers: BTreeMap<String, String>,
    pub metadata: BTreeMap<String, String>,
}

pub trait DomainService: Send + Sync {
    fn capabilities(&self) -> CapabilitySet;

    fn search<'a>(
        &'a self,
        context: &'a Context,
        query: SearchQuery,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>>;

    fn recommend<'a>(
        &'a self,
        context: &'a Context,
        request: RecommendationRequest,
    ) -> RuntimeFuture<'a, Vec<RankedCandidate>>;

    fn resolve<'a>(
        &'a self,
        context: &'a Context,
        request: ResolveRequest,
    ) -> RuntimeFuture<'a, ResolvedItem>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use edge_decision::{
        BooleanResult, ChoiceResult, DecisionKind, DecisionOutput, DecisionQuestion, DecisionState,
        DeterministicDecisionBackend, Probability, ScoreResult,
    };

    #[test]
    fn test_batch_evaluation_independent_routing() {
        let mut backend = DeterministicDecisionBackend::new();

        let item_q1 = DecisionItemResult {
            question_id: "media.route".to_string(),
            output: DecisionOutput::Choice(ChoiceResult {
                selected: "youtube".to_string(),
                probabilities: vec![Probability {
                    option: "youtube".to_string(),
                    probability: 0.94,
                }],
            }),
            confidence: 0.94,
            status: DecisionStatus::Accepted,
        };

        let item_q2 = DecisionItemResult {
            question_id: "kids.check".to_string(),
            output: DecisionOutput::Boolean(BooleanResult { probability: 0.98 }),
            confidence: 0.98,
            status: DecisionStatus::Accepted,
        };

        let item_q3 = DecisionItemResult {
            question_id: "human_review".to_string(),
            output: DecisionOutput::Boolean(BooleanResult { probability: 0.42 }),
            confidence: 0.42,
            status: DecisionStatus::Abstained,
        };

        let item_q4 = DecisionItemResult {
            question_id: "urgency.score".to_string(),
            output: DecisionOutput::Score(ScoreResult { value: 0.40 }),
            confidence: 0.40, // low confidence below minimum threshold 0.50
            status: DecisionStatus::Accepted,
        };

        backend.register(item_q1);
        backend.register(item_q2);
        backend.register(item_q3);
        backend.register(item_q4);

        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy {
            minimum_escalation_threshold: 0.50,
        });

        let input = DecisionInput {
            state: DecisionState::default(),
            questions: vec![
                DecisionQuestion {
                    id: "media.route".to_string(),
                    kind: DecisionKind::Choice,
                    options: vec!["youtube".to_string()],
                },
                DecisionQuestion {
                    id: "kids.check".to_string(),
                    kind: DecisionKind::Boolean,
                    options: vec![],
                },
                DecisionQuestion {
                    id: "human_review".to_string(),
                    kind: DecisionKind::Boolean,
                    options: vec![],
                },
                DecisionQuestion {
                    id: "urgency.score".to_string(),
                    kind: DecisionKind::Score,
                    options: vec![],
                },
            ],
        };

        let mut policies = HashMap::new();
        policies.insert(
            "media.route".to_string(),
            EscalationPolicy {
                threshold: 0.65,
                target: EscalationTarget::IntentModel,
            },
        );
        policies.insert(
            "kids.check".to_string(),
            EscalationPolicy {
                threshold: 0.90,
                target: EscalationTarget::Reject,
            },
        );
        policies.insert(
            "human_review".to_string(),
            EscalationPolicy {
                threshold: 0.70,
                target: EscalationTarget::Human,
            },
        );

        let batch_route = engine.evaluate(&backend, input, &policies).unwrap();
        assert_eq!(batch_route.items.len(), 4);

        // Q1: Execute (Accepted, 0.94 >= 0.65)
        match &batch_route.items[0] {
            DecisionRouteAction::Execute {
                effective_threshold,
                ..
            } => assert_eq!(*effective_threshold, 0.65),
            _ => panic!("Expected Execute for Q1"),
        }

        // Q2: Execute (Accepted, 0.98 >= 0.90)
        match &batch_route.items[1] {
            DecisionRouteAction::Execute {
                effective_threshold,
                ..
            } => assert_eq!(*effective_threshold, 0.90),
            _ => panic!("Expected Execute for Q2"),
        }

        // Q3: Escalate (Abstained -> Human)
        match &batch_route.items[3] {
            DecisionRouteAction::Escalate {
                effective_threshold,
                ..
            } => assert_eq!(*effective_threshold, 0.50),
            _ => panic!("Expected Escalate for Q4 due to safety floor"),
        }
    }

    #[test]
    fn test_backend_registry_resolution() {
        let mut registry = DecisionBackendRegistry::new();

        let mut jev_backend = DeterministicDecisionBackend::new();
        jev_backend.register(DecisionItemResult {
            question_id: "mobile.next_action".to_string(),
            output: DecisionOutput::Choice(ChoiceResult {
                selected: "tap".to_string(),
                probabilities: vec![],
            }),
            confidence: 0.91,
            status: DecisionStatus::Accepted,
        });

        registry.register(Arc::new(jev_backend));

        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy::default());

        let jev_input = DecisionInput {
            state: DecisionState::default(),
            questions: vec![DecisionQuestion {
                id: "mobile.next_action".to_string(),
                kind: DecisionKind::Choice,
                options: vec!["tap".to_string()],
            }],
        };

        let batch_route = engine
            .evaluate_registered(&registry, Some("deterministic"), jev_input, &HashMap::new())
            .unwrap();

        assert_eq!(batch_route.items.len(), 1);
        match &batch_route.items[0] {
            DecisionRouteAction::Execute { result, .. } => {
                if let DecisionOutput::Choice(c) = &result.output {
                    assert_eq!(c.selected, "tap");
                } else {
                    panic!("Expected Choice result");
                }
            }
            _ => panic!("Expected execution for registered backend"),
        }
    }
}
