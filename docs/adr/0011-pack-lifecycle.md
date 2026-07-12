# ADR 0011: Pack Lifecycle

## Status

Accepted

## Decision

Every pack follows the same lifecycle:

```text
Discover -> Download -> Verify -> Install -> Activate -> Update -> Deactivate -> Remove
```

Installed packs are immutable and read-only. User state is stored outside packs.

## Rationale

The lifecycle makes updates deterministic, allows dependency resolution, and
prevents knowledge updates from overwriting user history or preferences.

