# ADR 0002: ZIP Pack Format

## Status

Accepted

## Decision

Version 1 packs are single ZIP archives with immutable compiled knowledge,
indexes, metadata, assets, and signatures.

## Rationale

ZIP is easy to distribute, inspect, verify, update, and extend. Installed packs
are read-only; mutable user state is stored separately.

