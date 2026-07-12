# ADR 0013: Publishable Flutter SDK

## Status

Accepted

## Decision

The SLM repository publishes Edge Intelligence as an importable Flutter package
plus native Rust artifacts. Flutter applications consume the package through
use-case APIs and do not depend on Rust crates, repositories, pack internals, or
model runtime details.

## Rationale

SLM is the intelligence-building repository for multiple Flutter apps. Airo and
future apps should upgrade the intelligence layer by changing a package/artifact
version, not by copying source code or reimplementing platform logic.

