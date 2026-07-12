# ADR 0007: Search Engine

## Status

Accepted

## Decision

Retrieval and ranking are separate. Search returns candidates, and ranking
orders candidates using deterministic, configurable strategies.

## Rationale

This keeps experimentation with ranking independent from retrieval and avoids
letting AI decide playback.

