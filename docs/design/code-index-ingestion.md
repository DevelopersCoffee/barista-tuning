# Code Index Ingestion

## Objective

Compile offline code-index exports into the governed metadata catalog used by SLM
data generation and runtime retrieval. The interface must be deterministic,
vendor-neutral, provenance-preserving, and safe to use without copying raw code into
training data.

## Input contract

`Code Index Export v1` is JSON with:

- `schema_version`: `1.0`
- `knowledge_release`: immutable release identifier
- `source_revision`: repository commit or immutable revision
- `extractor`: `{id, version}`
- `symbols`: stable ID, kind, name, qualified name, language, relative path, line
  range, owner, and verification status
- `relationships`: subject ID, allowlisted predicate, object ID, and evidence location

Initial predicates use the existing catalog vocabulary: `IMPLEMENTS`, `EXPOSES`,
`INVOKES`, `READS_FROM`, `WRITES_TO`, `COMPUTES`, `PRODUCES`, and `CONSUMES`.

## Commands

```bash
slm compile-code-index examples/code_index/export.json --output build/code-index
pytest tests/test_code_index_ingestion.py
ruff check src tests
```

## Boundaries

- Always reject absolute paths, parent traversal, duplicate IDs, broken references,
  unsupported predicates, invalid line ranges, and mutable/missing revisions.
- Always derive evidence and catalog records deterministically.
- Never accept source bodies, secrets, credentials, SQL, shell, or generated actions.
- Never call a provider or production system during compilation.
- Provider adapters are future plugins; the core compiler accepts only the versioned
  interchange contract.

## Success criteria

- A valid export compiles into a catalog accepted by `validate_metadata_catalog`.
- Recompiling the same bytes produces byte-identical JSON.
- Every emitted entity and relationship has revisioned evidence.
- Invalid paths and references fail before any output is written.
- Tests require no network, code-index vendor, model, or cloud account.
