use std::collections::HashMap;

use crate::backend::DecisionBackend;
use crate::error::DecisionError;
use crate::types::{DecisionInput, DecisionItemResult, DecisionResult};
use crate::validation::validate_decision_input;

#[derive(Debug, Default)]
pub struct DeterministicDecisionBackend {
    responses: HashMap<String, DecisionItemResult>,
}

impl DeterministicDecisionBackend {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_response(mut self, item: DecisionItemResult) -> Self {
        self.responses.insert(item.question_id.clone(), item);
        self
    }

    pub fn register(&mut self, item: DecisionItemResult) {
        self.responses.insert(item.question_id.clone(), item);
    }
}

impl DecisionBackend for DeterministicDecisionBackend {
    fn id(&self) -> &str {
        "deterministic"
    }

    fn decide(&self, input: DecisionInput) -> Result<DecisionResult, DecisionError> {
        validate_decision_input(&input)?;

        let mut results = Vec::with_capacity(input.questions.len());

        for q in &input.questions {
            if let Some(res) = self.responses.get(&q.id) {
                results.push(res.clone());
            } else {
                return Err(DecisionError::new(format!(
                    "No deterministic response registered for question_id: '{}'",
                    q.id
                )));
            }
        }

        Ok(DecisionResult { results })
    }
}
