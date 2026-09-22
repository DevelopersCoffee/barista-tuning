use crate::error::DecisionError;
use crate::types::{DecisionInput, DecisionResult};

pub trait DecisionBackend: Send + Sync {
    fn decide(&self, input: DecisionInput) -> Result<DecisionResult, DecisionError>;
}
