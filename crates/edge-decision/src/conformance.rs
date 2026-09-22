use crate::backend::DecisionBackend;
use crate::error::DecisionError;
use crate::types::{DecisionInput, DecisionKind, DecisionQuestion, DecisionState};
use crate::validation::{validate_decision_input, validate_decision_item_result};

pub fn assert_backend_conformance(
    backend: &dyn DecisionBackend,
    sample_input: DecisionInput,
) -> Result<(), DecisionError> {
    if backend.id().trim().is_empty() {
        return Err(DecisionError::new("backend.id() must not be empty"));
    }

    validate_decision_input(&sample_input)?;

    let result = backend.decide(sample_input.clone())?;

    if result.results.len() != sample_input.questions.len() {
        return Err(DecisionError::new(format!(
            "backend '{}' returned {} results for {} questions",
            backend.id(),
            result.results.len(),
            sample_input.questions.len()
        )));
    }

    for (expected_q, item_res) in sample_input.questions.iter().zip(result.results.iter()) {
        validate_decision_item_result(item_res, Some(expected_q))?;
    }

    // Reject duplicate question IDs
    let duplicate_input = DecisionInput {
        state: DecisionState::default(),
        questions: vec![
            DecisionQuestion {
                id: "dup.q".to_string(),
                kind: DecisionKind::Boolean,
                options: vec![],
            },
            DecisionQuestion {
                id: "dup.q".to_string(),
                kind: DecisionKind::Boolean,
                options: vec![],
            },
        ],
    };

    if backend.decide(duplicate_input).is_ok() {
        return Err(DecisionError::new(
            "backend must reject DecisionInput containing duplicate question_ids",
        ));
    }

    Ok(())
}
