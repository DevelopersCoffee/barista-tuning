//! Runtime-level planner, decision execution engine, and domain service contracts.

#![forbid(unsafe_code)]

use std::collections::BTreeMap;
use std::future::Future;
use std::pin::Pin;

use edge_decision::{
    DecisionBackend, DecisionInput, DecisionResult, DecisionStatus, EscalationPolicy,
    EscalationTarget,
};
use edge_kernel::{CapabilitySet, Context, EdgeError, EdgeResult};
use edge_search::{RankedCandidate, SearchQuery};

pub type RuntimeFuture<'a, T> = Pin<Box<dyn Future<Output = EdgeResult<T>> + Send + 'a>>;

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
    fn test_low_confidence_triggers_escalation() {
        let mut backend = DeterministicDecisionBackend::new();
        let question_id = "media.route.uncertain";

        backend.register(
            question_id,
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "movie".to_string(),
                    probabilities: vec![Probability {
                        option: "movie".to_string(),
                        probability: 0.40,
                    }],
                }),
                confidence: 0.40,
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
                options: vec!["movie".to_string()],
            },
            payload: "Show something".to_string(),
        };

        let escalation = Some(EscalationPolicy {
            threshold: 0.65,
            target: EscalationTarget::GenerativeModel,
        });

        let action = engine.evaluate(&backend, input, escalation).unwrap();
        match action {
            DecisionRouteAction::Escalate {
                effective_threshold,
                target,
                ..
            } => {
                assert_eq!(effective_threshold, 0.65);
                assert_eq!(target, EscalationTarget::GenerativeModel);
            }
            DecisionRouteAction::Execute { .. } => panic!("Expected escalation"),
        }
    }

    #[test]
    fn test_abstained_status_triggers_escalation() {
        let mut backend = DeterministicDecisionBackend::new();
        let question_id = "safety.check";

        backend.register(
            question_id,
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "movie".to_string(),
                    probabilities: vec![],
                }),
                confidence: 0.80, // high confidence, but status is Abstained
                status: DecisionStatus::Abstained,
            },
        );

        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy {
            minimum_escalation_threshold: 0.50,
        });

        let input = DecisionInput {
            question: DecisionQuestion {
                id: question_id.to_string(),
                kind: DecisionKind::Choice,
                options: vec![],
            },
            payload: "Check content".to_string(),
        };

        let escalation = Some(EscalationPolicy {
            threshold: 0.60,
            target: EscalationTarget::Human,
        });

        let action = engine.evaluate(&backend, input, escalation).unwrap();
        match action {
            DecisionRouteAction::Escalate { target, .. } => {
                assert_eq!(target, EscalationTarget::Human);
            }
            DecisionRouteAction::Execute { .. } => panic!("Abstained result must escalate"),
        }
    }

    #[test]
    fn test_runtime_safety_floor_overrides_low_domain_threshold() {
        let mut backend = DeterministicDecisionBackend::new();
        let question_id = "payment.intent";

        backend.register(
            question_id,
            DecisionResult {
                output: DecisionOutput::Choice(ChoiceResult {
                    selected: "pay".to_string(),
                    probabilities: vec![],
                }),
                confidence: 0.70,
                status: DecisionStatus::Accepted,
            },
        );

        // Platform runtime requires minimum 0.90 threshold
        let engine = DecisionExecutionEngine::new(RuntimeDecisionPolicy {
            minimum_escalation_threshold: 0.90,
        });

        let input = DecisionInput {
            question: DecisionQuestion {
                id: question_id.to_string(),
                kind: DecisionKind::Choice,
                options: vec!["pay".to_string()],
            },
            payload: "Transfer money".to_string(),
        };

        // Domain DDL attempts to set dangerously low threshold of 0.10
        let escalation = Some(EscalationPolicy {
            threshold: 0.10,
            target: EscalationTarget::Reject,
        });

        let action = engine.evaluate(&backend, input, escalation).unwrap();
        match action {
            DecisionRouteAction::Escalate {
                effective_threshold,
                target,
                ..
            } => {
                // Effective threshold was raised by runtime safety floor to 0.90
                assert_eq!(effective_threshold, 0.90);
                assert_eq!(target, EscalationTarget::Reject);
            }
            DecisionRouteAction::Execute { .. } => {
                panic!("Runtime safety floor should have triggered escalation")
            }
        }
    }
}
