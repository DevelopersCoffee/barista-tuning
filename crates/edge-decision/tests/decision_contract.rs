use edge_decision::{
    BooleanResult, ChoiceResult, DecisionBackend, DecisionInput, DecisionKind, DecisionOutput,
    DecisionQuestion, DecisionResult, DecisionStatus, DeterministicDecisionBackend, Probability,
    ScoreResult,
};

#[test]
fn test_choice_accepted() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "media.route";

    let expected_result = DecisionResult {
        output: DecisionOutput::Choice(ChoiceResult {
            selected: "youtube".to_string(),
            probabilities: vec![
                Probability {
                    option: "youtube".to_string(),
                    probability: 0.92,
                },
                Probability {
                    option: "movie".to_string(),
                    probability: 0.08,
                },
            ],
        }),
        confidence: 0.92,
        status: DecisionStatus::Accepted,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Choice,
            options: vec!["youtube".to_string(), "movie".to_string()],
        },
        payload: "Play something fun".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Accepted);
    assert!(result.confidence >= 0.90);
}

#[test]
fn test_choice_abstained() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "media.route.ambiguous";

    let expected_result = DecisionResult {
        output: DecisionOutput::Choice(ChoiceResult {
            selected: "movie".to_string(),
            probabilities: vec![
                Probability {
                    option: "movie".to_string(),
                    probability: 0.45,
                },
                Probability {
                    option: "series".to_string(),
                    probability: 0.40,
                },
            ],
        }),
        confidence: 0.45,
        status: DecisionStatus::Abstained,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Choice,
            options: vec!["movie".to_string(), "series".to_string()],
        },
        payload: "Show that thing from last week".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Abstained);
}

#[test]
fn test_score_accepted() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "relevance.score";

    let expected_result = DecisionResult {
        output: DecisionOutput::Score(ScoreResult { value: 0.88 }),
        confidence: 0.95,
        status: DecisionStatus::Accepted,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Score,
            options: vec![],
        },
        payload: "Score document relevance".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Accepted);
}

#[test]
fn test_score_abstained() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "relevance.score.uncertain";

    let expected_result = DecisionResult {
        output: DecisionOutput::Score(ScoreResult { value: 0.50 }),
        confidence: 0.30,
        status: DecisionStatus::Abstained,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Score,
            options: vec![],
        },
        payload: "Score vague search query".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Abstained);
}

#[test]
fn test_boolean_accepted() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "safety.check";

    let expected_result = DecisionResult {
        output: DecisionOutput::Boolean(BooleanResult { probability: 0.99 }),
        confidence: 0.99,
        status: DecisionStatus::Accepted,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Boolean,
            options: vec!["true".to_string(), "false".to_string()],
        },
        payload: "Is content suitable for kids?".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Accepted);
}

#[test]
fn test_boolean_abstained() {
    let mut backend = DeterministicDecisionBackend::new();
    let question_id = "safety.check.uncertain";

    let expected_result = DecisionResult {
        output: DecisionOutput::Boolean(BooleanResult { probability: 0.52 }),
        confidence: 0.52,
        status: DecisionStatus::Abstained,
    };

    backend.register(question_id, expected_result.clone());

    let input = DecisionInput {
        question: DecisionQuestion {
            id: question_id.to_string(),
            kind: DecisionKind::Boolean,
            options: vec!["true".to_string(), "false".to_string()],
        },
        payload: "Is content suitable for general audience?".to_string(),
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result, expected_result);
    assert_eq!(result.status, DecisionStatus::Abstained);
}

#[test]
fn test_unregistered_question_error() {
    let backend = DeterministicDecisionBackend::new();
    let input = DecisionInput {
        question: DecisionQuestion {
            id: "unknown.question".to_string(),
            kind: DecisionKind::Choice,
            options: vec![],
        },
        payload: "test".to_string(),
    };

    let result = backend.decide(input);
    assert!(result.is_err());
    let err = result.unwrap_err();
    assert!(err.message.contains("unknown.question"));
}
