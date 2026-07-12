# ADR 0008: Compiler Pipeline

## Status

Accepted

## Decision

The compiler pipeline has three stages: ingestion, transformation, and
compilation.

## Rationale

Treating the compiler like a compiler makes test boundaries clear and allows
golden tests for pack output.

