//! Contract tests: schemas/intent/v1 is the single source of truth.

use std::fs;
use std::path::PathBuf;

fn schema_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../schemas/intent/v1")
}

fn compiled_schema() -> jsonschema::JSONSchema {
    let raw = fs::read_to_string(schema_dir().join("schema.json")).expect("read schema.json");
    let value: serde_json::Value = serde_json::from_str(&raw).expect("schema is JSON");
    jsonschema::JSONSchema::compile(&value).expect("schema compiles")
}

fn fixtures(sub: &str) -> Vec<(String, serde_json::Value)> {
    let dir = schema_dir().join("examples").join(sub);
    let mut out = Vec::new();
    for entry in fs::read_dir(&dir).unwrap_or_else(|_| panic!("missing dir {}", dir.display())) {
        let path = entry.expect("dir entry").path();
        let raw = fs::read_to_string(&path).expect("read fixture");
        let value = serde_json::from_str(&raw).expect("fixture is JSON");
        out.push((path.display().to_string(), value));
    }
    assert!(!out.is_empty(), "no fixtures in {}", dir.display());
    out
}

#[test]
fn valid_fixtures_pass_schema() {
    let schema = compiled_schema();
    for (name, value) in fixtures("valid") {
        assert!(schema.is_valid(&value), "expected valid: {name}");
    }
}

#[test]
fn invalid_fixtures_fail_schema() {
    let schema = compiled_schema();
    for (name, value) in fixtures("invalid") {
        assert!(!schema.is_valid(&value), "expected invalid: {name}");
    }
}

use edge_intent::command::IntentCommand;

#[test]
fn valid_fixtures_round_trip_through_rust_types() {
    for (name, value) in fixtures("valid") {
        let cmd: IntentCommand = serde_json::from_value(value.clone())
            .unwrap_or_else(|e| panic!("{name} must deserialize: {e}"));
        let back = serde_json::to_value(&cmd).expect("serialize");
        assert_eq!(value, back, "round-trip drift in {name}");
    }
}

#[test]
fn invalid_fixtures_rejected_by_rust_types() {
    for (name, value) in fixtures("invalid") {
        let parsed: Result<IntentCommand, _> = serde_json::from_value(value);
        assert!(parsed.is_err(), "expected Rust rejection: {name}");
    }
}

#[test]
fn rust_serialization_validates_against_schema() {
    // Drift check: anything the Rust types emit must satisfy schema.json.
    let schema = compiled_schema();
    for (name, value) in fixtures("valid") {
        let cmd: IntentCommand = serde_json::from_value(value).expect("deserialize");
        let emitted = serde_json::to_value(&cmd).expect("serialize");
        assert!(
            schema.is_valid(&emitted),
            "Rust output violates schema: {name}"
        );
    }
}

use edge_intent::command::FallbackReason;

#[test]
fn fallback_reason_serializes_as_tagged_json() {
    let cases: Vec<(FallbackReason, serde_json::Value)> = vec![
        (
            FallbackReason::InvalidOutput {
                detail: "unparseable".into(),
            },
            serde_json::json!({"reason": "invalid_output", "detail": "unparseable"}),
        ),
        (
            FallbackReason::LowConfidence {
                confidence: 0.31,
                threshold: 0.62,
            },
            serde_json::json!({"reason": "low_confidence", "confidence": 0.31, "threshold": 0.62}),
        ),
        (
            FallbackReason::Timeout,
            serde_json::json!({"reason": "timeout"}),
        ),
        (
            FallbackReason::BackendError {
                detail: "ffi panic".into(),
            },
            serde_json::json!({"reason": "backend_error", "detail": "ffi panic"}),
        ),
    ];
    for (reason, expected) in cases {
        let emitted = serde_json::to_value(&reason).expect("serialize");
        assert_eq!(expected, emitted);
        let back: FallbackReason = serde_json::from_value(emitted).expect("deserialize");
        assert_eq!(reason, back);
    }
}
