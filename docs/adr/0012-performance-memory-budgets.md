# ADR 0012: Performance and Memory Budgets

## Status

Accepted

## Decision

Initial edge-device budgets:

```text
Pack install: < 2 s
Pack load: < 500 ms
Search: < 30 ms
Recommendation: < 50 ms
Rule intent: < 5 ms
SLM intent: < 150 ms

Kernel: < 10 MB
SQLite cache: < 50 MB
Indexes: < 100 MB
Intent SLM: < 500 MB
Total runtime target: < 700 MB
```

## Rationale

Budgets force architectural choices to remain practical for Android TV,
Raspberry Pi, and commodity edge devices.

