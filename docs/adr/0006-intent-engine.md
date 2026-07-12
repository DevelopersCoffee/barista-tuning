# ADR 0006: Intent Engine

## Status

Accepted

## Decision

The intent engine is an internal SDK component with interchangeable backends:
rules, tiny SLM, larger SLM, remote, or hybrid.

## Rationale

Intent extraction can evolve without changing Flutter or pack formats. The SLM
is trained only for intent extraction, never provider knowledge.

