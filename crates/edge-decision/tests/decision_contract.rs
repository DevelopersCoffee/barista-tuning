use std::collections::BTreeMap;

use edge_decision::{
    BooleanResult, ChoiceResult, DecisionBackend, DecisionInput, DecisionItemResult,
    DecisionKind, DecisionOutput, DecisionQuestion, DecisionState, DecisionStatus,
    DeterministicDecisionBackend, Probability, ScoreResult,
};

#[test]
fn test_multi_question_single_pass_batch_evaluation() {
    let mut backend = DeterministicDecisionBackend::new();

    let item_q1 = DecisionItemResult {
        question_id: "media.route".to_string(),
        output: DecisionOutput::Choice(ChoiceResult {
            selected: "youtube".to_string(),
            probabilities: vec![
                Probability {
                    option: "youtube".to_string(),
                    probability: 0.94,
                },
                Probability {
                    option: "movie".to_string(),
                    probability: 0.06,
                },
            ],
        }),
        confidence: 0.94,
        status: DecisionStatus::Accepted,
    };

    let item_q2 = DecisionItemResult {
        question_id: "kids.check".to_string(),
        output: DecisionOutput::Boolean(BooleanResult { probability: 0.98 }),
        confidence: 0.98,
        status: DecisionStatus::Accepted,
    };

    let item_q3 = DecisionItemResult {
        question_id: "urgency.score".to_string(),
        output: DecisionOutput::Score(ScoreResult { value: 0.42 }),
        confidence: 0.42,
        status: DecisionStatus::Abstained,
    };

    backend.register(item_q1.clone());
    backend.register(item_q2.clone());
    backend.register(item_q3.clone());

    let mut attributes = BTreeMap::new();
    attributes.insert("current_screen".to_string(), "home".to_string());
    attributes.insert("user_profile".to_string(), "kids".to_string());

    let input = DecisionInput {
        state: DecisionState {
            attributes,
            payload: r#"{"user_request":"play something for kids"}"#.to_string(),
        },
        questions: vec![
            DecisionQuestion {
                id: "media.route".to_string(),
                kind: DecisionKind::Choice,
                options: vec!["youtube".to_string(), "movie".to_string()],
            },
            DecisionQuestion {
                id: "kids.check".to_string(),
                kind: DecisionKind::Boolean,
                options: vec!["true".to_string(), "false".to_string()],
            },
            DecisionQuestion {
                id: "urgency.score".to_string(),
                kind: DecisionKind::Score,
                options: vec![],
            },
        ],
    };

    let result = backend.decide(input).unwrap();
    assert_eq!(result.results.len(), 3);
    assert_eq!(result.results[0], item_q1);
    assert_eq!(result.results[1], item_q2);
    assert_eq!(result.results[2], item_q3);

    assert_eq!(result.results[0].status, DecisionStatus::Accepted);
    assert_eq!(result.results[1].status, DecisionStatus::Accepted);
    assert_eq!(result.results[2].status, DecisionStatus::Abstained);
}

#[test]
fn test_question_ordering_and_association_preserved() {
    let mut backend = DeterministicDecisionBackend::new();

    let item_a = DecisionItemResult {
        question_id: "question.a".to_string(),
        output: DecisionOutput::Boolean(BooleanResult { probability: 0.90 }),
        confidence: 0.90,
        status: DecisionStatus::Accepted,
    };

    let item_b = DecisionItemResult {
        question_id: "question.b".to_string(),
        output: DecisionOutput::Score(ScoreResult { value: 0.75 }),
        confidence: 0.75,
        status: DecisionStatus::Accepted,
    };

    backend.register(item_a.clone());
    backend.register(item_b.clone());

    let input_forward = DecisionInput {
        state: DecisionState::default(),
        questions: vec![
            DecisionQuestion {
                id: "question.a".to_string(),
                kind: DecisionKind::Boolean,
                options: vec![],
            },
            DecisionQuestion {
                id: "question.b".to_string(),
                kind: DecisionKind::Score,
                options: vec![],
            },
        ],
    };

    let res_forward = backend.decide(input_forward).unwrap();
    assert_eq!(res_forward.results[0].question_id, "question.a");
    assert_eq!(res_forward.results[1].question_id, "question.b");

    let input_reverse = DecisionInput {
        state: DecisionState::default(),
        questions: vec![
            DecisionQuestion {
                id: "question.b".to_string(),
                kind: DecisionKind::Score,
                options: vec![],
            },
            DecisionQuestion {
                id: "question.a".to_string(),
                kind: DecisionKind::Boolean,
                options: vec![],
            },
        ],
    };

    let res_reverse = backend.decide(input_reverse).unwrap();
    assert_eq!(res_reverse.results[0].question_id, "question.b");
    assert_eq!(res_reverse.results[1].question_id, "question.a");
}

#[test]
fn test_unregistered_question_error() {
    let backend = DeterministicDecisionBackend::new();
    let input = DecisionInput {
        state: DecisionState::default(),
        questions: vec![DecisionQuestion {
            id: "unknown.question".to_string(),
            kind: DecisionKind::Choice,
            options: vec![],
        }],
    };

    let result = backend.decide(input);
    assert!(result.is_err());
    let err = result.unwrap_err();
    assert!(err.message.contains("unknown.question"));
}
