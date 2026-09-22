//! Compiler-stage contracts: ingestion, transformation, compilation, and Domain IR decision definitions.

#![forbid(unsafe_code)]

use edge_decision::{DecisionKind, EscalationPolicy};
use edge_kernel::{EdgeError, EdgeResult};
use edge_pack::PackManifest;

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionQuestionSpec {
    pub id: String,
    pub kind: DecisionKind,
    pub options: Vec<String>,
    pub escalation: Option<EscalationPolicy>,
}

impl DecisionQuestionSpec {
    pub fn validate(&self, decision_id: &str) -> EdgeResult<()> {
        if self.id.trim().is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                format!("question id is required in decision '{}'", decision_id),
            ));
        }

        if self.kind == DecisionKind::Choice && self.options.is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                format!(
                    "question '{}' of type choice in decision '{}' requires at least one option",
                    self.id, decision_id
                ),
            ));
        }

        if let Some(ref policy) = self.escalation {
            if !(0.0..=1.0).contains(&policy.threshold) {
                return Err(EdgeError::new(
                    edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                    format!(
                        "question '{}' in decision '{}' escalation threshold must be between 0.0 and 1.0, got {}",
                        self.id, decision_id, policy.threshold
                    ),
                ));
            }
        }

        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionDefinition {
    pub id: String,
    pub state_fields: Vec<String>,
    pub questions: Vec<DecisionQuestionSpec>,
    pub backend: Option<String>,
}

impl DecisionDefinition {
    pub fn validate(&self) -> EdgeResult<()> {
        if self.id.trim().is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                "decision id is required",
            ));
        }

        if self.questions.is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                format!("decision '{}' requires at least one question", self.id),
            ));
        }

        for q in &self.questions {
            q.validate(&self.id)?;
        }

        if let Some(ref b) = self.backend {
            if b.trim().is_empty() {
                return Err(EdgeError::new(
                    edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                    format!("decision '{}' backend type cannot be empty", self.id),
                ));
            }
        }

        Ok(())
    }
}

pub trait IngestionStage<Source, RawIr> {
    fn ingest(&self, source: Source) -> EdgeResult<RawIr>;
}

pub trait TransformationStage<RawIr, DomainIr> {
    fn transform(&self, raw: RawIr) -> EdgeResult<DomainIr>;
}

pub trait CompilationStage<DomainIr> {
    fn compile(&self, ir: DomainIr, output_path: &str) -> EdgeResult<PackManifest>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompileReport {
    pub source_count: usize,
    pub emitted_items: usize,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationReport {
    pub error_count: usize,
    pub warning_count: usize,
    pub messages: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use edge_decision::EscalationTarget;

    #[test]
    fn test_valid_multi_question_decision_definition() {
        let def = DecisionDefinition {
            id: "media.route".to_string(),
            state_fields: vec!["user_request".to_string(), "current_screen".to_string()],
            questions: vec![
                DecisionQuestionSpec {
                    id: "provider".to_string(),
                    kind: DecisionKind::Choice,
                    options: vec!["youtube".to_string(), "movie".to_string()],
                    escalation: Some(EscalationPolicy {
                        threshold: 0.65,
                        target: EscalationTarget::IntentModel,
                    }),
                },
                DecisionQuestionSpec {
                    id: "kids_content".to_string(),
                    kind: DecisionKind::Boolean,
                    options: vec![],
                    escalation: Some(EscalationPolicy {
                        threshold: 0.90,
                        target: EscalationTarget::Reject,
                    }),
                },
            ],
            backend: Some("laya".to_string()),
        };
        assert!(def.validate().is_ok());
    }

    #[test]
    fn test_empty_questions_fails_validation() {
        let def = DecisionDefinition {
            id: "bad.decision".to_string(),
            state_fields: vec![],
            questions: vec![],
            backend: None,
        };
        let res = def.validate();
        assert!(res.is_err());
        assert!(res.unwrap_err().message.contains("requires at least one question"));
    }
}
