# ADR 0017: Vendor-Neutral Code Index Ingestion Boundary

## Status

Accepted

## Decision

Introduce `Code Index Export v1` as the offline boundary between code-intelligence
tools and the governed enterprise metadata catalog. The export contains symbol
identity, kind, language, repository-relative location, source revision, extractor
lineage, and typed relationships. It does not contain raw source bodies, secrets,
credentials, runtime data, or executable instructions.

The compiler validates references and paths, creates deterministic evidence records,
and emits the existing metadata catalog contract. Code-intelligence vendors and
open-source indexers remain replaceable producers of the same export.

## Rationale

Training and runtime retrieval should not depend directly on a proprietary index or
send entire source files into model prompts. A small deterministic interchange format
preserves provenance and makes changes reproducible while allowing specialized
extractors to evolve independently.

## Consequences

- Index adapters must translate provider-specific output into Code Index Export v1.
- Only repository-relative paths and allowlisted relationship types are accepted.
- Raw code retrieval remains a separately authorized runtime operation.
- The first slice compiles symbols and relationships; API/workflow-specific parsers
  can add richer typed records behind the same boundary later.
