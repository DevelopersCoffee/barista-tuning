# ADR 0001: Rust-First Core

## Status

Accepted

## Decision

Edge Intelligence uses a Rust-first core. Flutter is a UI and playback layer
accessing the core through a thin FFI wrapper.

## Rationale

Rust gives the platform one reusable implementation for desktop, Android,
Android TV, Raspberry Pi, and embedded ARM targets while keeping business logic
outside Flutter.

