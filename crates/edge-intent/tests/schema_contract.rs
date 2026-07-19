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
