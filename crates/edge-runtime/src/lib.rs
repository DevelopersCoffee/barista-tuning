//! Runtime-level planner, decision execution engine, backend registry, and domain service contracts.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, HashMap};
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;

use edge_decision::{
    DecisionBackend, DecisionInput, DecisionResult, DecisionStatus, EscalationPolicy,
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

    pub fn register(&mut self, name: impl Into<String>, backend: Arc<dyn DecisionBackend>) {
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
        result: DecisionResult,
        effective_threshold: f32,
    },
    Escalate {
        result: DecisionResult,
        effective_threshold: f32,
        target: EscalationTarget,
    },
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
        escalation: Option<EscalationPolicy>,
    ) -> EdgeResult<DecisionRouteAction> {
        let domain_threshold = escalation.as_ref().map(|p| p.threshold).unwrap_or(0.0);
        let effective_threshold = domain_threshold.max(self.policy.minimum_escalation_threshold);
        let target = escalation
            .as_ref()
            .map(|p| p.target)
            .unwrap_or(EscalationTarget::IntentModel);

        let result = backend.decide(input).map_err(|e| {
            EdgeError::new(edge_kernel::errors::EdgeErrorKind::Internal, e.message)
        })?;

        if result.status == DecisionStatus::Accepted && result.confidence >= effective_threshold {
            Ok(DecisionRouteAction::Execute {
                result,
                effective_threshold,
            })
        } else {
            Ok(DecisionRouteAction::Escalate {
                result,
                effective_threshold,
                target,
            })
        }
    }

    pub fn evaluate_registered(
        &self,
        registry: &DecisionBackendRegistry,
        preferred_backend: Option<&str>,
        input: DecisionInput,
        escalation: Option<EscalationPolicy>,
    ) -> EdgeResult<DecisionRouteAction> {
        let backend = registry.resolve(preferred_backend)?;
        self.evaluate(backend.as_ref(), input, escalation)
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
        ChoiceResult, DecisionKind, DecisionOutput, DecisionQuestion,
        DeterministicDecisionBackend, Probability,
    };

    #[test]
    fn test_accepted_high_confidence_executes_fast_path() {
        let mut backend = DeterministicDecisionBackend::new();
        let question_id = "media.route";

        backend.register(
            question_id,
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "youtube".to_string(),
                    probabilities: vec![Probability {
                        option: "youtube".to_string(),
                        probability: 0.92,
                    }],
                }),
                confidence: 0.92,
                status: DecisionStatus::Accepted,
            },
        );

        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy {
            minimum_escalation_threshold: 0.50,
        });

        let input = DecisionInput {
            question: DecisionQuestion {
                id: question_id.to_string(),
                kind: DecisionKind::Choice,
                options: vec!["youtube".to_string()],
            },
            payload: "Play music".to_string(),
        };

        let escalation = Some(EscalationPolicy {
            threshold: 0.65,
            target: EscalationTarget::IntentModel,
        });

        let action = engine.evaluate(&backend, input, escalation).unwrap();
        match action {
            DecisionRouteAction::Execute {
                effective_threshold,
                result,
            } => {
                assert_eq!(effective_threshold, 0.65);
                assert_eq!(result.status, DecisionStatus::Accepted);
            }
            DecisionRouteAction::Escalate { .. } => panic!("Expected fast-path execution"),
        }
    }

    #[test]
    fn test_backend_registry_resolution() {
        let mut registry = DecisionBackendRegistry::new();

        let mut laya_backend = DeterministicDecisionBackend::new();
        laya_backend.register(
            "media.route",
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "movie".to_string(),
                    probabilities: vec![],
                }),
                confidence: 0.95,
                status: DecisionStatus::Accepted,
            },
        );

        let mut jev_backend = DeterministicDecisionBackend::new();
        jev_backend.register(
            "mobile.next_action",
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "tap".to_string(),
                    probabilities: vec![],
                }),
                confidence: 0.91,
                status: DecisionStatus::Accepted,
            },
        );

        registry.register("laya", Arc::new(laya_backend));
        registry.register("jev", Arc::new(jev_backend));

        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy::default());

        let jev_input = DecisionInput {
            question: DecisionQuestion {
                id: "mobile.next_action".to_string(),
                kind: DecisionKind::Choice,
                options: vec!["tap".to_string()],
            },
            payload: "screen".to_string(),
        };

        let action = engine
            .evaluate_registered(&registry, Some("jev"), jev_input, None)
            .unwrap();

        match action {
            DecisionRouteAction::Execute { result, .. } => {
                if let DecisionOutput::Choice(c) = result.output {
                    assert_eq!(c.selected, "tap");
                } else {
                    panic!("Expected Choice result");
                }
            }
            _ => panic!("Expected execution for registered Jev backend"),
        }
    }

    #[test]
    fn test_unregistered_backend_returns_error() {
        let registry = DecisionBackendRegistry::new();
        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy::default());

        let input = DecisionInput {
            question: DecisionQuestion {
                id: "test".to_string(),
                kind: DecisionKind::Choice,
                options: vec![],
            },
            payload: "".to_string(),
        };

        let result = engine.evaluate_registered(&registry, Some("unknown_backend"), input, None);
        assert!(result.is_err());
        assert!(result.unwrap_err().message.contains("not registered"));
    }
}
