# ADR 0005: FFI Boundary

## Status

Accepted

## Decision

Bindings expose use cases, not engines or repositories. Flutter calls APIs such
as install pack, search, recommend, resolve, and play.

The Rust FFI crate is the only crate allowed to expose C ABI symbols. Other
crates keep unsafe code forbidden.

## Rationale

The application should never depend on SQLite, search engines, intent backends,
or pack internals.
