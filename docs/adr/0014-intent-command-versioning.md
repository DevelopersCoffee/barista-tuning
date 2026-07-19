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
