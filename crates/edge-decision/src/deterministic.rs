use std::collections::HashMap;

use crate::backend::DecisionBackend;
use crate::error::DecisionError;
use crate::types::{DecisionInput, DecisionResult};

#[derive(Debug, Default)]
pub struct DeterministicDecisionBackend {
    responses: HashMap<String, DecisionResult>,
}

impl DeterministicDecisionBackend {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_response(mut self, question_id: impl Into<String>, result: DecisionResult) -> Self {
        self.responses.insert(question_id.into(), result);
        self
    }

    pub fn register(&mut self, question_id: impl Into<String>, result: DecisionResult) {
        self.responses.insert(question_id.into(), result);
    }
}

impl DecisionBackend for DeterministicDecisionBackend {
    fn decide(&self, input: DecisionInput) -> Result<DecisionResult, DecisionError> {
        if let Some(res) = self.responses.get(&input.question.id) {
            Ok(res.clone())
        } else {
            Err(DecisionError::new(format!(
                "No deterministic response registered for question_id: '{}'",
                input.question.id
            )))
        }
    }
}
