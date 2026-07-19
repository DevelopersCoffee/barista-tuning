# Intent Engine Phase 1: IntentCommand Schema + Rust Types + Entity Vocab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship IntentCommand v1 as the canonical versioned schema with validated Rust types in `edge-intent`, plus the `edge-media` entity vocabulary used for grounding and dataset generation.

**Architecture:** Replace the pre-release `schemas/intent/v1/schema.json` wholesale with the IntentCommand shape from the approved spec ([design](../specs/2026-07-19-intent-engine-v1-design.md)). New serde types live in a new `command` module of `crates/edge-intent` alongside the existing `IntentResult` (which stays untouched until Phase 3). Entity vocab is one canonical JSON file inside `crates/edge-media`, embedded into Rust via `include_str!` and read by the Phase-2 Python dataset generator from the same path — single source of truth by construction.

**Tech Stack:** Rust (serde, serde_json, jsonschema dev-dep), JSON Schema draft 2020-12.

**Spec:** `docs/superpowers/specs/2026-07-19-intent-engine-v1-design.md` — issues #2 and #8 (entity-vocab half).

## Global Constraints

- Schema path is exactly `schemas/intent/v1/schema.json`; `$id` is `https://edge-intelligence.local/schemas/intent/v1/schema.json`.
- v1 intents enum, exactly: `browse`, `play`, `resume`, `similar`, `search`.
- Entity types, exactly: `team`, `sport`, `league`, `genre`, `language`, `channel`, `title`.
- `additionalProperties: false` on every object in the schema; `#[serde(deny_unknown_fields)]` on every Rust struct mirroring it.
- Versioning rule: additive-only within v1.x; enum extension = minor bump; field removal/rename = v2 (ADR in Task 2).
- Do NOT modify or remove the existing `IntentResult` types or any backend in `crates/edge-intent/src/lib.rs` — Phase 3 migrates them.
- Rust gates that must stay green after every task: `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`.
- Commit after every task; conventional-commit messages.

## File Structure

```
schemas/intent/v1/schema.json                      REPLACE — IntentCommand v1
schemas/intent/v1/examples/valid/*.json            CREATE — 3 canonical fixtures
schemas/intent/v1/examples/invalid/*.json          CREATE — 3 rejection fixtures
docs/adr/0014-intent-command-versioning.md         CREATE — versioning rule
crates/edge-intent/Cargo.toml                      MODIFY — add serde; dev-dep jsonschema
crates/edge-intent/src/lib.rs                      MODIFY — add `pub mod command;` line only
crates/edge-intent/src/command.rs                  CREATE — IntentCommand types + FallbackReason
crates/edge-intent/tests/schema_contract.rs        CREATE — fixture validation + round-trip + drift tests
crates/edge-media/data/entities_v1.json            CREATE — canonical entity vocab
crates/edge-media/src/lib.rs                       MODIFY — add `pub mod vocab;` line only
crates/edge-media/src/vocab.rs                     CREATE — EntityVocab load/ground API
```

---

### Task 1: IntentCommand v1 JSON Schema + fixtures

**Files:**
- Modify: `schemas/intent/v1/schema.json` (full replace of content)
- Create: `schemas/intent/v1/examples/valid/browse_india_today.json`
- Create: `schemas/intent/v1/examples/valid/play_minimal.json`
- Create: `schemas/intent/v1/examples/valid/search_sorted.json`
- Create: `schemas/intent/v1/examples/invalid/missing_intent.json`
- Create: `schemas/intent/v1/examples/invalid/bad_intent_enum.json`
- Create: `schemas/intent/v1/examples/invalid/extra_field.json`
- Create: `crates/edge-intent/tests/schema_contract.rs`
- Modify: `crates/edge-intent/Cargo.toml`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `schemas/intent/v1/schema.json` (draft 2020-12) and six fixture files at the exact paths above. Task 3 round-trips the valid fixtures; Phase-3/4 code validates model output against this schema file.

- [ ] **Step 1: Add jsonschema dev-dependency**

In `crates/edge-intent/Cargo.toml`, change the `[dev-dependencies]` section to:

```toml
[dev-dependencies]
tempfile = "3"
jsonschema = "0.18"
```

- [ ] **Step 2: Write the failing test**

Create `crates/edge-intent/tests/schema_contract.rs`:

```rust
//! Contract tests: schemas/intent/v1 is the single source of truth.

use std::fs;
use std::path::PathBuf;

fn schema_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../schemas/intent/v1")
}

fn compiled_schema() -> jsonschema::JSONSchema {
    let raw = fs::read_to_string(schema_dir().join("schema.json")).expect("read schema.json");
    let value: serde_json::Value = serde_json::from_str(&raw).expect("schema is JSON");
    jsonschema::JSONSchema::options()
        .with_draft(jsonschema::Draft::Draft202012)
        .compile(&value)
        .expect("schema compiles")
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: FAIL — either "missing dir .../examples/valid" or `valid_fixtures_pass_schema` fails, because the current `schema.json` still has the old `{constraints, missing_fields, clarification_required}` shape and no examples exist.

- [ ] **Step 4: Replace schema.json**

Replace the entire content of `schemas/intent/v1/schema.json` with:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://edge-intelligence.local/schemas/intent/v1/schema.json",
  "title": "IntentCommand 1.0",
  "type": "object",
  "required": ["intent", "entities", "filters", "sort", "confidence", "schema_version"],
  "additionalProperties": false,
  "properties": {
    "intent": {
      "type": "string",
      "enum": ["browse", "play", "resume", "similar", "search"]
    },
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "value"],
        "additionalProperties": false,
        "properties": {
          "type": {
            "type": "string",
            "enum": ["team", "sport", "league", "genre", "language", "channel", "title"]
          },
          "value": { "type": "string", "minLength": 1 },
          "grounded_id": { "type": "string", "minLength": 1 }
        }
      }
    },
    "filters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["field", "op", "value"],
        "additionalProperties": false,
        "properties": {
          "field": { "type": "string", "minLength": 1 },
          "op": {
            "type": "string",
            "enum": ["eq", "neq", "lt", "lte", "gt", "gte", "range", "in"]
          },
          "value": {
            "type": ["string", "number", "boolean", "array"],
            "items": { "type": ["string", "number"] }
          }
        }
      }
    },
    "sort": {
      "oneOf": [
        { "type": "null" },
        {
          "type": "object",
          "required": ["field", "order"],
          "additionalProperties": false,
          "properties": {
            "field": { "type": "string", "minLength": 1 },
            "order": { "type": "string", "enum": ["asc", "desc"] }
          }
        }
      ]
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "schema_version": { "type": "string", "const": "1.0" }
  }
}
```

- [ ] **Step 5: Create valid fixtures**

`schemas/intent/v1/examples/valid/browse_india_today.json` (the proof-point query "show every India match today"):

```json
{
  "intent": "browse",
  "entities": [
    { "type": "team", "value": "India", "grounded_id": "team:india" },
    { "type": "sport", "value": "match", "grounded_id": "sport:cricket" }
  ],
  "filters": [
    { "field": "time", "op": "eq", "value": "today" }
  ],
  "sort": null,
  "confidence": 0.93,
  "schema_version": "1.0"
}
```

`schemas/intent/v1/examples/valid/play_minimal.json`:

```json
{
  "intent": "play",
  "entities": [
    { "type": "title", "value": "planet earth" }
  ],
  "filters": [],
  "sort": null,
  "confidence": 0.71,
  "schema_version": "1.0"
}
```

`schemas/intent/v1/examples/valid/search_sorted.json`:

```json
{
  "intent": "search",
  "entities": [
    { "type": "genre", "value": "comedy", "grounded_id": "genre:comedy" },
    { "type": "language", "value": "hindi", "grounded_id": "lang:hi" }
  ],
  "filters": [
    { "field": "kid_safe", "op": "eq", "value": true }
  ],
  "sort": { "field": "release_date", "order": "desc" },
  "confidence": 0.88,
  "schema_version": "1.0"
}
```

- [ ] **Step 6: Create invalid fixtures**

`schemas/intent/v1/examples/invalid/missing_intent.json`:

```json
{
  "entities": [],
  "filters": [],
  "sort": null,
  "confidence": 0.5,
  "schema_version": "1.0"
}
```

`schemas/intent/v1/examples/invalid/bad_intent_enum.json`:

```json
{
  "intent": "recommend",
  "entities": [],
  "filters": [],
  "sort": null,
  "confidence": 0.5,
  "schema_version": "1.0"
}
```

`schemas/intent/v1/examples/invalid/extra_field.json`:

```json
{
  "intent": "browse",
  "entities": [],
  "filters": [],
  "sort": null,
  "confidence": 0.5,
  "schema_version": "1.0",
  "provider": "netflix"
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: PASS — both `valid_fixtures_pass_schema` and `invalid_fixtures_fail_schema`.

- [ ] **Step 8: Run workspace gates**

Run: `cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace`
Expected: all green (no existing code referenced the old schema file).

- [ ] **Step 9: Commit**

```bash
git add schemas/intent/v1 crates/edge-intent/Cargo.toml crates/edge-intent/tests/schema_contract.rs
git commit -m "feat(schema): replace intent v1 with IntentCommand contract"
```

---

### Task 2: ADR 0014 — IntentCommand versioning rule

**Files:**
- Create: `docs/adr/0014-intent-command-versioning.md`

**Interfaces:**
- Consumes: Task 1 schema.
- Produces: the versioning rule later phases and the Airo drift-check cite. No code.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0014-intent-command-versioning.md`:

```markdown
# ADR 0014: IntentCommand Schema Versioning

## Status

Accepted

## Decision

`schemas/intent/v1/schema.json` (IntentCommand) evolves additive-only within
major version 1:

- Adding an optional field, or extending an enum (new intent, entity type,
  filter op): minor bump (1.0 -> 1.1). Consumers pinned to an older minor
  keep working.
- Removing or renaming a field, changing a type, or tightening a constraint:
  major bump (v2 at `schemas/intent/v2/`). v1 remains frozen.
- `schema_version` inside each IntentCommand is the emitting model's schema
  version; the engine rejects a pack whose schema major differs from the
  engine's supported major.

Airo vendors the schema at a pinned version; a CI drift check compares the
vendored hash against this repo's released tag. Additive-only within v1.x
makes lagging a minor version safe.

## Rationale

Airo and this repo release independently. An additive-only contract lets the
model artifact, the engine, and the app upgrade on separate cadences without
coordination, while the major version is the single hard compatibility gate.
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/0014-intent-command-versioning.md
git commit -m "docs(adr): record IntentCommand additive-only versioning rule"
```

---

### Task 3: Rust IntentCommand types + round-trip + drift tests

**Files:**
- Create: `crates/edge-intent/src/command.rs`
- Modify: `crates/edge-intent/src/lib.rs` (add one line: `pub mod command;` directly after the crate doc comment)
- Modify: `crates/edge-intent/Cargo.toml` (add serde with derive)
- Modify: `crates/edge-intent/tests/schema_contract.rs` (append round-trip + drift tests)

**Interfaces:**
- Consumes: Task 1 schema + valid fixtures.
- Produces (Phase 3/4/5 rely on these exact names):
  - `edge_intent::command::IntentCommand { intent: Intent, entities: Vec<Entity>, filters: Vec<Filter>, sort: Option<Sort>, confidence: f64, schema_version: String }`
  - `enum Intent { Browse, Play, Resume, Similar, Search }` (serde lowercase)
  - `struct Entity { r#type: EntityType, value: String, grounded_id: Option<String> }`
  - `enum EntityType { Team, Sport, League, Genre, Language, Channel, Title }` (serde lowercase)
  - `struct Filter { field: String, op: FilterOp, value: serde_json::Value }`
  - `enum FilterOp { Eq, Neq, Lt, Lte, Gt, Gte, Range, In }` (serde lowercase)
  - `struct Sort { field: String, order: SortOrder }`, `enum SortOrder { Asc, Desc }` (serde lowercase)

- [ ] **Step 1: Add serde dependency**

In `crates/edge-intent/Cargo.toml`, change `[dependencies]` to:

```toml
[dependencies]
edge-kernel = { path = "../edge-kernel" }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

- [ ] **Step 2: Write the failing tests**

Append to `crates/edge-intent/tests/schema_contract.rs`:

```rust
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
        assert!(schema.is_valid(&emitted), "Rust output violates schema: {name}");
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: COMPILE FAIL — `edge_intent::command` module does not exist yet.

- [ ] **Step 4: Implement the types**

Create `crates/edge-intent/src/command.rs`:

```rust
//! IntentCommand v1 — Rust mirror of schemas/intent/v1/schema.json.
//! Additive-only within v1.x (ADR 0014).

use serde::{Deserialize, Serialize};

pub const SCHEMA_VERSION: &str = "1.0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IntentCommand {
    pub intent: Intent,
    pub entities: Vec<Entity>,
    pub filters: Vec<Filter>,
    pub sort: Option<Sort>,
    pub confidence: f64,
    pub schema_version: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Intent {
    Browse,
    Play,
    Resume,
    Similar,
    Search,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entity {
    #[serde(rename = "type")]
    pub entity_type: EntityType,
    pub value: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub grounded_id: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EntityType {
    Team,
    Sport,
    League,
    Genre,
    Language,
    Channel,
    Title,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Filter {
    pub field: String,
    pub op: FilterOp,
    pub value: serde_json::Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FilterOp {
    Eq,
    Neq,
    Lt,
    Lte,
    Gt,
    Gte,
    Range,
    In,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Sort {
    pub field: String,
    pub order: SortOrder,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SortOrder {
    Asc,
    Desc,
}
```

In `crates/edge-intent/src/lib.rs`, add directly after the crate doc comment (line 1):

```rust
pub mod command;
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: PASS — all five tests.

Note: if `invalid_fixtures_rejected_by_rust_types` fails on `extra_field.json` only, `deny_unknown_fields` is missing on `IntentCommand`; if it fails on `missing_intent.json`, a field wrongly has a `#[serde(default)]`. Fix the derive attributes, not the fixtures.

- [ ] **Step 6: Run workspace gates**

Run: `cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add crates/edge-intent
git commit -m "feat(intent): add IntentCommand v1 rust types with schema drift tests"
```

---

### Task 4: FallbackReason contract type

**Files:**
- Modify: `crates/edge-intent/src/command.rs` (append)
- Modify: `crates/edge-intent/tests/schema_contract.rs` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces (Phase 3 OutputPipeline and Phase 5 FFI rely on this exact shape):
  - `edge_intent::command::FallbackReason` — tagged JSON `{"reason": "invalid_output" | "low_confidence" | "timeout" | "backend_error", ...detail fields}`
  - `type ResolveOutcome = Result<IntentCommand, FallbackReason>`

- [ ] **Step 1: Write the failing test**

Append to `crates/edge-intent/tests/schema_contract.rs`:

```rust
use edge_intent::command::FallbackReason;

#[test]
fn fallback_reason_serializes_as_tagged_json() {
    let cases: Vec<(FallbackReason, serde_json::Value)> = vec![
        (
            FallbackReason::InvalidOutput { detail: "unparseable".into() },
            serde_json::json!({"reason": "invalid_output", "detail": "unparseable"}),
        ),
        (
            FallbackReason::LowConfidence { confidence: 0.31, threshold: 0.62 },
            serde_json::json!({"reason": "low_confidence", "confidence": 0.31, "threshold": 0.62}),
        ),
        (FallbackReason::Timeout, serde_json::json!({"reason": "timeout"})),
        (
            FallbackReason::BackendError { detail: "ffi panic".into() },
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: COMPILE FAIL — `FallbackReason` not defined.

- [ ] **Step 3: Implement**

Append to `crates/edge-intent/src/command.rs`:

```rust
/// Terminal non-command outcome. Airo maps every variant to deterministic
/// search; the variant is telemetry, not a UX branch (spec: Adoption req. 3).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "reason", rename_all = "snake_case", deny_unknown_fields)]
pub enum FallbackReason {
    InvalidOutput { detail: String },
    LowConfidence { confidence: f64, threshold: f64 },
    Timeout,
    BackendError { detail: String },
}

/// The total output type of `resolve()`: command or explicit fallback, never
/// free text.
pub type ResolveOutcome = Result<IntentCommand, FallbackReason>;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cargo test -p edge-intent --test schema_contract`
Expected: PASS.

- [ ] **Step 5: Run workspace gates**

Run: `cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add crates/edge-intent
git commit -m "feat(intent): add FallbackReason contract type"
```

---

### Task 5: edge-media entity vocabulary

**Files:**
- Create: `crates/edge-media/data/entities_v1.json`
- Create: `crates/edge-media/src/vocab.rs`
- Modify: `crates/edge-media/src/lib.rs` (add one line: `pub mod vocab;` directly after the crate doc comment)
- Modify: `crates/edge-media/Cargo.toml` (add serde with derive)

**Interfaces:**
- Consumes: nothing from earlier tasks (deliberately decoupled: vocab stores entity type as plain string so edge-media gains no edge-intent dependency; Phase 3 grounding code, which lives in edge-intent, converts `EntityType` to its lowercase string form when calling).
- Produces:
  - Canonical vocab file `crates/edge-media/data/entities_v1.json` — Phase-2 Python dataset generator reads this exact path.
  - `edge_media::vocab::EntityVocab::load_default() -> EdgeResult<EntityVocab>`
  - `EntityVocab::from_json(json: &str) -> EdgeResult<EntityVocab>`
  - `EntityVocab::ground(&self, entity_type: &str, surface: &str) -> Option<&str>` — returns canonical id (e.g. `"team:india"`) for a surface form, after normalization (trim, lowercase, collapse internal whitespace). Entity type strings are the schema enum values: `team|sport|league|genre|language|channel|title`.
  - `EntityVocab::entries(&self, entity_type: &str) -> Vec<(&str, &str)>` — (canonical_id, display_name) pairs, for dataset generation and eval ablation.

- [ ] **Step 1: Create the vocab data file**

Create `crates/edge-media/data/entities_v1.json`. Seed set — real entries, extended in Phase 2 as dataset generation demands:

```json
{
  "vocab_version": "1.0",
  "entities": {
    "team": [
      { "id": "team:india", "name": "India", "aliases": ["india", "team india", "ind", "bharat", "india ka", "indian team"] },
      { "id": "team:pakistan", "name": "Pakistan", "aliases": ["pakistan", "pak"] },
      { "id": "team:australia", "name": "Australia", "aliases": ["australia", "aus", "aussies"] },
      { "id": "team:england", "name": "England", "aliases": ["england", "eng"] },
      { "id": "team:csk", "name": "Chennai Super Kings", "aliases": ["csk", "chennai", "chennai super kings"] },
      { "id": "team:mi", "name": "Mumbai Indians", "aliases": ["mi", "mumbai", "mumbai indians"] }
    ],
    "sport": [
      { "id": "sport:cricket", "name": "Cricket", "aliases": ["cricket", "match", "cricket match"] },
      { "id": "sport:football", "name": "Football", "aliases": ["football", "soccer"] },
      { "id": "sport:tennis", "name": "Tennis", "aliases": ["tennis"] },
      { "id": "sport:kabaddi", "name": "Kabaddi", "aliases": ["kabaddi"] }
    ],
    "league": [
      { "id": "league:ipl", "name": "IPL", "aliases": ["ipl", "indian premier league"] },
      { "id": "league:epl", "name": "Premier League", "aliases": ["epl", "premier league", "english premier league"] },
      { "id": "league:isl", "name": "ISL", "aliases": ["isl", "indian super league"] }
    ],
    "genre": [
      { "id": "genre:comedy", "name": "Comedy", "aliases": ["comedy", "funny", "comedy shows"] },
      { "id": "genre:drama", "name": "Drama", "aliases": ["drama"] },
      { "id": "genre:news", "name": "News", "aliases": ["news", "khabar", "samachar"] },
      { "id": "genre:kids", "name": "Kids", "aliases": ["kids", "cartoon", "cartoons", "bacchon ka"] },
      { "id": "genre:devotional", "name": "Devotional", "aliases": ["devotional", "bhakti", "bhajan"] }
    ],
    "language": [
      { "id": "lang:hi", "name": "Hindi", "aliases": ["hindi", "hindi me", "hindi mein"] },
      { "id": "lang:en", "name": "English", "aliases": ["english", "english me", "angrezi"] },
      { "id": "lang:ta", "name": "Tamil", "aliases": ["tamil"] },
      { "id": "lang:te", "name": "Telugu", "aliases": ["telugu"] }
    ],
    "channel": [
      { "id": "channel:star_sports", "name": "Star Sports", "aliases": ["star sports", "star sports 1"] },
      { "id": "channel:sony_sports", "name": "Sony Sports", "aliases": ["sony sports", "sony ten", "ten sports"] },
      { "id": "channel:dd_national", "name": "DD National", "aliases": ["dd national", "doordarshan"] }
    ],
    "title": []
  }
}
```

- [ ] **Step 2: Write the failing tests**

Create `crates/edge-media/src/vocab.rs` containing ONLY the test module for now:

```rust
//! Entity vocabulary for intent slot grounding and dataset generation.
//! Canonical data: crates/edge-media/data/entities_v1.json.

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn load_default_succeeds() {
        let vocab = EntityVocab::load_default().expect("embedded vocab loads");
        assert!(!vocab.entries("team").is_empty());
    }

    #[test]
    fn grounds_exact_alias() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "india"), Some("team:india"));
        assert_eq!(vocab.ground("league", "indian premier league"), Some("league:ipl"));
    }

    #[test]
    fn grounds_hinglish_alias() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "india ka"), Some("team:india"));
        assert_eq!(vocab.ground("genre", "bacchon ka"), Some("genre:kids"));
    }

    #[test]
    fn normalizes_case_and_whitespace() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "  Team   INDIA "), Some("team:india"));
    }

    #[test]
    fn unknown_surface_returns_none() {
        let vocab = EntityVocab::load_default().unwrap();
        assert_eq!(vocab.ground("team", "atlantis"), None);
        assert_eq!(vocab.ground("nonsense_type", "india"), None);
    }

    #[test]
    fn rejects_malformed_json() {
        assert!(EntityVocab::from_json("{\"vocab_version\": \"1.0\"}").is_err());
        assert!(EntityVocab::from_json("not json").is_err());
    }

    #[test]
    fn entries_lists_canonical_pairs() {
        let vocab = EntityVocab::load_default().unwrap();
        let teams = vocab.entries("team");
        assert!(teams.contains(&("team:india", "India")));
    }
}
```

In `crates/edge-media/src/lib.rs`, add directly after the crate doc comment (line 1):

```rust
pub mod vocab;
```

In `crates/edge-media/Cargo.toml`, change `[dependencies]` to add serde:

```toml
[dependencies]
edge-kernel = { path = "../edge-kernel" }
edge-runtime = { path = "../edge-runtime" }
edge-search = { path = "../edge-search" }
rusqlite = { version = "0.32", features = ["bundled"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cargo test -p edge-media vocab`
Expected: COMPILE FAIL — `EntityVocab` not defined.

- [ ] **Step 4: Implement EntityVocab**

Insert into `crates/edge-media/src/vocab.rs`, above the test module:

```rust
use std::collections::BTreeMap;

use edge_kernel::errors::EdgeErrorKind;
use edge_kernel::{EdgeError, EdgeResult};
use serde::Deserialize;

const EMBEDDED_VOCAB: &str = include_str!("../data/entities_v1.json");

#[derive(Debug, Deserialize)]
struct VocabFile {
    #[allow(dead_code)]
    vocab_version: String,
    entities: BTreeMap<String, Vec<VocabEntry>>,
}

#[derive(Debug, Deserialize)]
struct VocabEntry {
    id: String,
    name: String,
    aliases: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct EntityVocab {
    /// entity_type -> normalized alias -> canonical id
    alias_index: BTreeMap<String, BTreeMap<String, String>>,
    /// entity_type -> (canonical id, display name), file order
    entries: BTreeMap<String, Vec<(String, String)>>,
}

fn normalize(surface: &str) -> String {
    surface
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}

impl EntityVocab {
    pub fn load_default() -> EdgeResult<Self> {
        Self::from_json(EMBEDDED_VOCAB)
    }

    pub fn from_json(json: &str) -> EdgeResult<Self> {
        let file: VocabFile = serde_json::from_str(json).map_err(|e| {
            EdgeError::new(EdgeErrorKind::InvalidArgument, format!("vocab parse: {e}"))
        })?;
        let mut alias_index: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
        let mut entries: BTreeMap<String, Vec<(String, String)>> = BTreeMap::new();
        for (entity_type, list) in file.entities {
            let type_aliases = alias_index.entry(entity_type.clone()).or_default();
            let type_entries = entries.entry(entity_type).or_default();
            for entry in list {
                type_aliases.insert(normalize(&entry.name), entry.id.clone());
                for alias in &entry.aliases {
                    type_aliases.insert(normalize(alias), entry.id.clone());
                }
                type_entries.push((entry.id, entry.name));
            }
        }
        Ok(Self { alias_index, entries })
    }

    /// Canonical id for a surface form, or None if ungrounded.
    pub fn ground(&self, entity_type: &str, surface: &str) -> Option<&str> {
        self.alias_index
            .get(entity_type)?
            .get(&normalize(surface))
            .map(String::as_str)
    }

    /// (canonical_id, display_name) pairs for one entity type.
    pub fn entries(&self, entity_type: &str) -> Vec<(&str, &str)> {
        self.entries
            .get(entity_type)
            .map(|list| {
                list.iter()
                    .map(|(id, name)| (id.as_str(), name.as_str()))
                    .collect()
            })
            .unwrap_or_default()
    }
}
```

`EdgeErrorKind::InvalidArgument` is a real variant — see `crates/edge-kernel/src/errors.rs:7`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cargo test -p edge-media vocab`
Expected: PASS — all seven tests.

- [ ] **Step 6: Run workspace gates**

Run: `cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add crates/edge-media
git commit -m "feat(media): add entity vocabulary with hinglish alias grounding"
```

---

### Task 6: Close out issue #2 scope — schema drift documentation

**Files:**
- Modify: `schemas/intent/v1/schema.json` — no change; verification only
- Create: `docs/design/intent-command-drift-check.md`

**Interfaces:**
- Consumes: Tasks 1–4 artifacts.
- Produces: the documented drift-check procedure issue #2 acceptance requires ("Airo side imports/vendors identical schema version; drift check documented").

- [ ] **Step 1: Write the drift-check doc**

Create `docs/design/intent-command-drift-check.md`:

```markdown
# IntentCommand Schema Drift Check

Two consumers must agree on `schemas/intent/v1/schema.json`:

1. **This repo (Rust).** `crates/edge-intent/tests/schema_contract.rs` is the
   in-repo drift gate: valid fixtures round-trip through the Rust types
   byte-for-byte, invalid fixtures are rejected by both the schema and the
   types, and everything the Rust types serialize re-validates against
   `schema.json`. Any divergence between types and schema fails
   `cargo test --workspace`.

2. **Airo (vendored copy).** Airo vendors `schema.json` at a pinned release
   tag of this repo. Airo CI recomputes `sha256sum schema.json` for its
   vendored copy and compares it to the hash of the same file at the pinned
   tag here. Mismatch fails Airo CI with instructions to re-vendor.

Versioning rule: ADR 0014 (additive-only within v1.x). Because minors are
additive, Airo may lag minor versions safely; a major bump requires an
explicit re-vendor and an engine upgrade.

Verify current hash:

    sha256sum schemas/intent/v1/schema.json
```

- [ ] **Step 2: Run full gates one final time**

Run: `cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings && cargo test --workspace && pytest`
Expected: all green (pytest confirms no Python test referenced the old schema shape).

- [ ] **Step 3: Commit**

```bash
git add docs/design/intent-command-drift-check.md
git commit -m "docs(intent): document schema drift check for airo vendoring"
```

---

## Phase Exit Criteria (maps to issue acceptance)

- Issue #2: schema validation rejects malformed output in tests (Task 1, Task 3); Rust types round-trip (Task 3); versioning ADR (Task 2); drift check documented (Task 6). Issue #2 closeable after this phase.
- Issue #8 (vocab half): entity vocab with Hinglish aliases shipped and tested (Task 5). Slot-F1 ablation acceptance stays open until Phase 4 eval harness exists.
- Phases 2–5 planned separately after this phase lands (spec: Issue Mapping table).
