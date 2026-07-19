# IntentCommand Schema Drift Check

Two consumers must agree on `schemas/intent/v1/schema.json`:

1. **This repo (Rust).** `crates/edge-intent/tests/schema_contract.rs` is the
   in-repo drift gate: valid fixtures round-trip through the Rust types
   byte-for-byte, and invalid fixtures are rejected by both the schema and
   the types. This proves the Rust types enforce **structure and enums** —
   required fields, field names (`#[serde(deny_unknown_fields)]`), and enum
   variants — in agreement with `schema.json`.

   It does **not** prove the Rust types enforce value-level constraints that
   serde can't structurally express: `confidence` range (`0..=1`),
   `schema_version` const (`"1.0"`), `minLength: 1` on string fields
   (`value`, `grounded_id`, `field`), or `Filter.value`'s restriction to
   string/number/boolean/array (Rust's `serde_json::Value` also accepts
   objects and null). A payload that violates one of these constraints can
   still deserialize successfully into the Rust types. Catching those
   requires validating the raw JSON against `schema.json` directly, which is
   Phase 3/4's `OutputPipeline` responsibility (parse → schema-validate →
   semantic-validate), not something `cargo test`'s drift tests cover today.

2. **Airo (vendored copy).** Airo vendors `schema.json` at a pinned release
   tag of this repo. Airo CI recomputes `sha256sum schema.json` for its
   vendored copy and compares it to the hash of the same file at the pinned
   tag here. Mismatch fails Airo CI with instructions to re-vendor.

Versioning rule: ADR 0014 (additive-only within v1.x). Because minors are
additive, Airo may lag minor versions safely; a major bump requires an
explicit re-vendor and an engine upgrade.

Verify current hash:

    sha256sum schemas/intent/v1/schema.json
