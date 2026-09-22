use std::collections::HashSet;

use crate::error::DecisionError;
use crate::types::{
    DecisionInput, DecisionItemResult, DecisionKind, DecisionOutput, DecisionQuestion,
};

pub fn validate_decision_question(question: &DecisionQuestion) -> Result<(), DecisionError> {
    if question.id.trim().is_empty() {
        return Err(DecisionError::new("question id must not be empty"));
    }

    if question.kind == DecisionKind::Choice && question.options.is_empty() {
        return Err(DecisionError::new(format!(
            "question '{}' of kind Choice requires at least one option",
            question.id
        )));
    }

    Ok(())
}

pub fn validate_decision_input(input: &DecisionInput) -> Result<(), DecisionError> {
    if input.questions.is_empty() {
        return Err(DecisionError::new("DecisionInput requires at least one question"));
    }

    let mut seen_ids = HashSet::new();

    for q in &input.questions {
        validate_decision_question(q)?;
        if !seen_ids.insert(&q.id) {
            return Err(DecisionError::new(format!(
                "duplicate question_id '{}' found in DecisionInput",
                q.id
            )));
        }
    }

    Ok(())
}

pub fn validate_decision_item_result(
    item: &DecisionItemResult,
    expected_question: Option<&DecisionQuestion>,
) -> Result<(), DecisionError> {
    if item.question_id.trim().is_empty() {
        return Err(DecisionError::new("DecisionItemResult question_id must not be empty"));
    }

    if !(0.0..=1.0).contains(&item.confidence) {
        return Err(DecisionError::new(format!(
            "question '{}' confidence must be between 0.0 and 1.0, got {}",
            item.question_id, item.confidence
        )));
    }

    match &item.output {
        DecisionOutput::Choice(c) => {
            for prob in &c.probabilities {
                if !(0.0..=1.0).contains(&prob.probability) {
                    return Err(DecisionError::new(format!(
                        "question '{}' option '{}' probability must be in [0,1], got {}",
                        item.question_id, prob.option, prob.probability
                    )));
                }
            }
        }
        DecisionOutput::Score(s) => {
            if !(0.0..=1.0).contains(&s.value) {
                return Err(DecisionError::new(format!(
                    "question '{}' score value must be in [0,1], got {}",
                    item.question_id, s.value
                )));
            }
        }
        DecisionOutput::Boolean(b) => {
            if !(0.0..=1.0).contains(&b.probability) {
                return Err(DecisionError::new(format!(
                    "question '{}' boolean probability must be in [0,1], got {}",
                    item.question_id, b.probability
                )));
            }
        }
    }

    if let Some(q) = expected_question {
        if item.question_id != q.id {
            return Err(DecisionError::new(format!(
                "expected result for question_id '{}', got '{}'",
                q.id, item.question_id
            )));
        }

        match (&q.kind, &item.output) {
            (DecisionKind::Choice, DecisionOutput::Choice(_)) => {}
            (DecisionKind::Score, DecisionOutput::Score(_)) => {}
            (DecisionKind::Boolean, DecisionOutput::Boolean(_)) => {}
            (expected_kind, actual_output) => {
                return Err(DecisionError::new(format!(
                    "question '{}' expects kind {:?}, got incompatible output {:?}",
                    q.id, expected_kind, actual_output
                )));
            }
        }
    }

    Ok(())
}
