use crate::error::DecisionError;
use crate::types::{DecisionInput, DecisionResult};

pub trait DecisionBackend: Send + Sync {
    /// Returns the unique string identifier for this decision backend
    /// (e.g. "deterministic", "laya", "jev").
    fn id(&self) -> &str;

    /// Evaluates a single-pass multi-question decision input over structured state.
    fn decide(&self, input: DecisionInput) -> Result<DecisionResult, DecisionError>;
}
