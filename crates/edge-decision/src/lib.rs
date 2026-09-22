#![forbid(unsafe_code)]

pub mod backend;
pub mod conformance;
pub mod deterministic;
pub mod error;
pub mod types;
pub mod validation;

pub use backend::DecisionBackend;
pub use conformance::assert_backend_conformance;
pub use deterministic::DeterministicDecisionBackend;
pub use error::DecisionError;
pub use types::*;
pub use validation::{
    validate_decision_input, validate_decision_item_result, validate_decision_question,
};
