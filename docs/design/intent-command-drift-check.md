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
