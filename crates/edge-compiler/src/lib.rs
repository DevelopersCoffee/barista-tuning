//! Compiler-stage contracts: ingestion, transformation, compilation, and Domain IR decision definitions.

#![forbid(unsafe_code)]

use edge_decision::{DecisionKind, EscalationPolicy};
use edge_kernel::{EdgeError, EdgeResult};
use edge_pack::PackManifest;

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionDefinition {
    pub id: String,
    pub kind: DecisionKind,
    pub options: Vec<String>,
    pub backend: Option<String>,
    pub escalation: Option<EscalationPolicy>,
}

impl DecisionDefinition {
    pub fn validate(&self) -> EdgeResult<()> {
        if self.id.trim().is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                "decision id is required",
            ));
        }

        if self.kind == DecisionKind::Choice && self.options.is_empty() {
            return Err(EdgeError::new(
                edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                format!("decision '{}' of type choice requires at least one option", self.id),
            ));
        }

        if let Some(ref b) = self.backend {
            if b.trim().is_empty() {
                return Err(EdgeError::new(
                    edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                    format!("decision '{}' backend type cannot be empty", self.id),
                ));
            }
        }

        if let Some(ref policy) = self.escalation {
            if !(0.0..=1.0).contains(&policy.threshold) {
                return Err(EdgeError::new(
                    edge_kernel::errors::EdgeErrorKind::InvalidArgument,
                    format!(
                        "decision '{}' escalation threshold must be between 0.0 and 1.0, got {}",
                        self.id, policy.threshold
                    ),
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
    fn test_valid_decision_definition() {
        let def = DecisionDefinition {
            id: "media.route".to_string(),
            kind: DecisionKind::Choice,
            options: vec!["youtube".to_string(), "movie".to_string()],
            backend: Some("laya".to_string()),
            escalation: Some(EscalationPolicy {
                threshold: 0.65,
                target: EscalationTarget::IntentModel,
            }),
        };
        assert!(def.validate().is_ok());
    }

    #[test]
    fn test_valid_jev_decision_definition() {
        let def = DecisionDefinition {
            id: "mobile.next_action".to_string(),
            kind: DecisionKind::Choice,
            options: vec!["tap".to_string(), "scroll".to_string()],
            backend: Some("jev".to_string()),
            escalation: Some(EscalationPolicy {
                threshold: 0.70,
                target: EscalationTarget::IntentModel,
            }),
        };
        assert!(def.validate().is_ok());
    }

    #[test]
    fn test_choice_without_options_fails_validation() {
        let def = DecisionDefinition {
            id: "bad.choice".to_string(),
            kind: DecisionKind::Choice,
            options: vec![],
            backend: None,
            escalation: None,
        };
        let res = def.validate();
        assert!(res.is_err());
        assert!(res.unwrap_err().message.contains("requires at least one option"));
    }

    #[test]
    fn test_invalid_threshold_fails_validation() {
        let def = DecisionDefinition {
            id: "bad.threshold".to_string(),
            kind: DecisionKind::Boolean,
            options: vec![],
            backend: None,
            escalation: Some(EscalationPolicy {
                threshold: 1.5,
                target: EscalationTarget::GenerativeModel,
            }),
        };
        let res = def.validate();
        assert!(res.is_err());
        assert!(res.unwrap_err().message.contains("between 0.0 and 1.0"));
    }
}
