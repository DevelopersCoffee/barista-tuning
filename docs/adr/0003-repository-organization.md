# ADR 0003: Repository Organization

## Status

Accepted

## Decision

The repository is split into kernel, platform, domain, compiler, CLI, bindings,
schemas, docs, and tests. The kernel has no dependency on media or any other
domain.

## Rationale

This keeps dependency direction explicit and prevents the core runtime from
becoming a media-specific framework.

