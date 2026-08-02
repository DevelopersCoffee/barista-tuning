# ADR 0016: Portable Training Backends

## Status

Accepted

## Decision

Separate the training contract from its execution engine and hosting provider.
Pipeline configuration selects either `transformers` or `mlx`. Transformers/PEFT
remains the default and portable CUDA/CPU engine. MLX-LM is an optional Apple
Silicon engine. Backend-specific data is derived from the same validated SFT rows.

A portable training-job directory is the handoff boundary for remote compute. It
contains a rewritten configuration, required local inputs, SHA-256 checksums, and
the framework command to execute. It contains no credentials and does not submit
work to a provider. Colab, Hugging Face, GCP, or an internal runner may transport
and execute that directory under its own identity and policy.

## Rationale

The existing MPS and CPU measurements are too slow and unstable for the
context-matched experiment. Apple MLX is optimized for unified memory on Apple
Silicon, while Transformers/PEFT is broadly supported by CUDA cloud workers.
Keeping provider selection outside the model pipeline avoids duplicated training
logic, vendor lock-in, and evaluation drift.

## Consequences

- Existing configurations remain backward compatible.
- MLX is an optional platform dependency and cannot run on non-Apple hosts.
- Backend artifacts may have different physical formats, but all candidates must
  pass the same held-out evaluation and release requirements.
- Cloud execution, cost approval, identity, encryption, and data residency remain
  deployment concerns rather than implicit CLI side effects.
