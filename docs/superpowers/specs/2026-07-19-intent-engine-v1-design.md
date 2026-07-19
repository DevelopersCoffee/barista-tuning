# Airo v0.0.5 Intent Engine v1 — Design

Date: 2026-07-19
Status: Approved (brainstorming session)
Epic: DevelopersCoffee/barista-tuning#1 (child issues #2–#8)
Airo counterparts: airo#898 (epic), airo#904 (integration), airo#899, airo#901, airo#905, airo#906, airo#907

## Goal

Natural-language query → schema-valid `IntentCommand` JSON, fully on-device,
< 1.5 s on Fire TV Stick class hardware, ≥ 90% exact-intent match on the
50-query canonical eval set. Proof-point query: "show every India match today"
(and Hinglish "India ka match dikhao").

This repo owns everything from query text to validated IntentCommand. Airo
never runs AI logic; it consumes an immutable pack and executes commands
deterministically.

## Key Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | Architecture design + task breakdown derived from it |
| 2 | Runtime backends | Dual in v0.0.5: GGUF/llama.cpp AND LiteRT, both latency-validated |
| 3 | Schema conflict | IntentCommand replaces existing `schemas/intent/v1` wholesale (pre-release, nothing consumes old shape) |
| 4 | Base model | SmolLM2-360M primary, SmolLM2-135M challenger; eval gate picks |
| 5 | Constraint strategy | Pluggable seam; ship Grammar (llama.cpp GBNF) + Unconstrained (LiteRT); TokenMask reserved as extension point |
| 6 | Dataset size | Maximized: ≥ 10k examples (stretch 20k) — accuracy first; SLM must nail its one narrow job |

## Architecture Overview

```
User NL query ("show every India match today" / "India ka match dikhao")
        │
        ▼
┌─ Airo app (Flutter) ────────────────────────────────┐
│  core_edge_intelligence → FFI call: resolve(text)   │
└──────────────────┬──────────────────────────────────┘
                   ▼  edge-ffi boundary
┌─ This repo owns everything below ───────────────────┐
│ edge-intent :: IntentEngine                         │
│   1. PromptTemplate (from pack)                     │
│   2. IntentBackend (trait):                         │
│        LlamaCppBackend | LiteRtBackend              │
│      └ ConstraintStrategy:                          │
│        Grammar | Unconstrained | TokenMask (later)  │
│   3. OutputPipeline (invariant, backend-agnostic):  │
│      parse → schema-validate → semantic-validate    │
│      (entity grounding via edge-media vocab)        │
│      → retry-once (repair prompt)                   │
│      → Ok(IntentCommand) | Fallback(reason)         │
│   4. ConfidenceScorer (logprob-based);              │
│      threshold τ from pack manifest                 │
└──────────────────┬──────────────────────────────────┘
                   ▼
   IntentCommand v1 JSON  {intent, entities[], filters[], sort, confidence}
   or Fallback signal → Airo deterministic search
```

Everything model-adjacent (weights, prompt template, schema version, grammar,
threshold, eval-report hash) travels inside one immutable edge-pack. Airo never
sees a model — only pack + `resolve(query) → IntentCommand | Fallback`.

Training side (offline, this repo): dataset JSONL → SFT config → tuned
checkpoint (360M primary, 135M challenger) → eval gate → dual export (GGUF
quantized + LiteRT quantized) → pack build.

### Constraint strategy: two layers, pluggable

- **Layer 1 (best-effort, per-backend):** llama.cpp path uses a GBNF grammar
  compiled from the IntentCommand schema — output structurally valid by
  construction. LiteRT path ships Unconstrained day one and relies on Layer 2.
  `TokenMask` (schema-guided logit masking over both runtimes) is a named
  extension point for a later milestone; nothing in schema, pack, or FFI
  assumes which strategy produced output.
- **Layer 2 (guarantee, invariant):** the OutputPipeline in `edge-intent` is
  the contract issue #4 tests. The fuzz gate runs against it regardless of
  backend or strategy.

## Components & Contracts (issues #2, #8)

### `schemas/intent/v1` — IntentCommand (issue #2)

Replaces the existing schema shape at the same path.

```json
{
  "intent": "browse | play | resume | similar | search",
  "entities": [
    {"type": "team|sport|league|genre|language|channel|title",
     "value": "...", "grounded_id": "optional"}
  ],
  "filters": [
    {"field": "time|kid_safe|live|...", "op": "eq|range|...", "value": "..."}
  ],
  "sort": {"field": "...", "order": "asc|desc"},
  "confidence": 0.0,
  "schema_version": "1.0"
}
```

- `additionalProperties: false` everywhere. `sort` nullable.
- Versioning rule (new ADR): additive-only within v1.x; enum extension =
  minor bump; field removal/rename = v2.
- Entity/filter vocab cross-referenced against `schemas/airo-media-actions`
  and `schemas/media-ir`.
- Rust types in `crates/edge-intent` with round-trip serde tests against
  schema fixtures. Drift check: CI test validates Rust serialization against
  `schema.json`.

### `crates/edge-intent` — IntentEngine

- Traits: `IntentBackend` (infer), `ConstraintStrategy`, `ConfidenceScorer`.
  `OutputPipeline` is concrete and invariant.
- Public API: `resolve(query: &str) → Result<IntentCommand, FallbackReason>`
  plus `load_pack(path)`.
- `FallbackReason` enum: `InvalidOutput`, `LowConfidence`, `Timeout`,
  `BackendError`. Airo maps all to deterministic search; reasons feed
  telemetry only.

### `crates/edge-media` — entity vocab pack (issue #8)

- Sports / leagues / teams / genres / languages / channel aliases with
  canonical IDs + alias tables, including Hinglish aliases
  ("India ka match" → team:india).
- Used in two places: (a) semantic validation/grounding in OutputPipeline —
  an ungrounded entity is not a hard failure; it passes through without
  `grounded_id`; (b) dataset generation vocabulary, so train/serve vocab is
  identical by construction.
- Acceptance: entity grounding measurably improves slot F1 on the eval set
  vs. a no-pack baseline (ablation).

### `crates/edge-profile` — watch-pattern features (issue #8)

- Rule-based, no LLM. Contract: synthetic history in → deterministic feature
  vector out (time-of-day, day-of-week, channel/genre recurrence).
- Versioned schema: new `schemas/profile-features/v1`.
- Consumed by Airo's routine detector (airo#905, airo#907). Independent of the
  intent path; only shared surface is pack distribution.

## Training, Data & Confidence (issues #3, #6)

### Dataset (≥ 10k examples, stretch 20k; `{instruction, input, output}` JSONL)

- Generation: template grammar over `edge-media` vocab (intents × entities ×
  time filters × kid/family constraints) → LLM paraphrase augmentation for
  naturalness → human spot-review sample (~10%).
- Scale guards: near-duplicate dedup (normalized-query hashing);
  contamination check — zero overlap with the 50-query eval set (exact +
  fuzzy); per-intent / entity-type / language distribution balance report in
  the data card so no intent starves.
- Languages: English + Hindi/Hinglish, Devanagari and romanized both
  ("India ka match dikhao", "इंडिया का मैच दिखाओ"). Target ≥ 30% Hinglish share.
- Negative/ambiguous set (~10% of total): out-of-domain queries and
  unresolvable references with low-confidence targets — teaches the model to
  signal uncertainty rather than hallucinate slots.
- Output side: canonical IntentCommand JSON, compact (no whitespace), fixed
  key order — eases grammar decoding and exact-match eval.
- Lineage in data card (`docs/`): generator version, vocab version,
  augmentation model, review protocol.
- Two configs under `configs/`: `airo_intent_sft_360m.yaml` (primary),
  `airo_intent_sft_135m.yaml` (challenger). Same dataset, same eval;
  artifact reproducible from config alone.

### Confidence (issue #6)

- Method: sequence-logprob — mean token logprob over the generated JSON,
  mapped through a calibration curve into the `confidence` field. No extra
  head (keeps export simple across GGUF + LiteRT).
- Calibration: reliability curve on the eval set; fit temperature or isotonic
  mapping; pick default threshold τ where above-τ precision ≥ 95%.
- Contract: τ is versioned in the pack manifest, not hard-coded in Airo.
  Below τ ⇒ `FallbackReason::LowConfidence`. The engine applies the threshold
  internally — Airo receives command-or-fallback, never interprets raw
  confidence. Confidence remains in IntentCommand for telemetry.

### Risk: LiteRT logprob availability

If the LiteRT runtime cannot expose token logprobs on-device, fallback plan is
a length-normalized score from an output re-scoring pass. Verify early —
first spike of the packaging track.

## Eval Gate & Packaging (issues #5, #7)

### Eval harness (issue #5)

- 50-query canonical set + expected IntentCommand fixtures in
  `tests/eval/intent_v1/`. Covers all 5 intents (incl. resume/similar per
  airo#906), routine-style queries, Hinglish share matching the dataset, and
  the proof-point query verbatim.
- Metrics: exact-intent match, slot F1 (entity + filter level),
  schema-validity-or-fallback rate, latency p50/p95.
- Release thresholds: ≥ 90% exact-intent; 100% schema-valid-or-fallback;
  above-τ precision ≥ 95%. Slot F1 tracked from the baseline run; its gate
  threshold is set after baseline and hardened in v1.1.
- Runs via the existing eval command; report → `reports/` (JSON + markdown).
  Report hash embedded in the pack manifest — a pack is cryptographically
  tied to the eval that cleared it.
- Gate: release script refuses pack build if thresholds miss; documented for
  CI and local. Same harness runs against both backends (GGUF on dev machine,
  LiteRT via on-device runner or emulator) and both model sizes — the
  360M-vs-135M decision comes from this table.

### Packaging (issue #7)

- Export: tuned checkpoint → (a) GGUF quantized (Q4_K_M starting point;
  measure quality delta vs f16) under `gguf/`; (b) LiteRT quantized
  (int8 dynamic-range starting point).
- Pack contents via `crates/edge-pack` contract: model artifact(s),
  `schemas/intent/v1/schema.json`, prompt template, GBNF grammar (llama.cpp
  variant), threshold τ, eval report hash, `pack-manifest` with
  schema_version + model lineage.
- Latency budget: query → IntentCommand < 1.5 s end-to-end on Fire TV Stick
  class, measured per backend per model size, recorded in the eval report.
  Breakdown target: prompt eval + generation ≤ 1.2 s, pipeline overhead ≤ 0.3 s.
- Immutability + version negotiation: pack hash check on load; engine rejects
  a pack whose schema_version major ≠ engine's supported major. Both tested.
- FFI notes updated (`bindings/flutter`, `crates/edge-ffi`). Surface:
  `load_pack(path)` + `resolve(query) → json | fallback`.

## Error Handling & Testing

### Error handling (issue #4 core)

- Every failure path terminates in `FallbackReason` — no panic, no free text
  ever crossing FFI. `resolve()` is total: `IntentCommand | FallbackReason`.
- Retry policy: exactly one repair attempt (re-prompt with validator error
  hint), then fallback. Retry is deadline-aware: if the first attempt is
  already near budget, skip retry and fall back.
- Timeout: hard deadline inside the engine (from pack config, default 1.5 s)
  → `FallbackReason::Timeout`.
- FFI: errors serialize as tagged JSON across the boundary; Rust panics
  caught at the FFI layer (`catch_unwind`) → `BackendError`. Never abort the
  host app.

### Testing

- Schema round-trip: Rust types ↔ `schema.json` fixtures, valid + malformed
  corpus (issue #2 acceptance).
- Fuzz gate: 1k adversarial/garbage prompts → 100% valid-or-fallback, zero
  panics (issue #4 acceptance). Runs both shipped constraint strategies —
  proving the invariant holds without grammar means the LiteRT path is safe.
- Eval harness (above) = model-quality tests.
- `edge-media` grounding: slot-F1 ablation with/without entity pack.
- `edge-profile`: golden tests — synthetic history → expected feature vector.
- Pack: immutability (hash tamper → load reject) and version negotiation
  (major mismatch → reject) tests.

## Adoption Requirements (Airo side)

This repo's deliverable is this contract; Airo's implementation is tracked in
airo#898/#904.

1. **Pack loading.** Load the edge-pack from app storage via FFI
   `load_pack(path)`; honor rejection (hash/version mismatch) by staying on
   deterministic search. No pack unbundling — the pack is opaque + immutable.
2. **Single call surface.** `resolve(query) → IntentCommand | Fallback`.
   Airo executes IntentCommand deterministically in its media engine; never
   edits or reinterprets fields; never applies its own confidence logic —
   the threshold is applied engine-side.
3. **Fallback behavior.** Every `FallbackReason` → deterministic search path
   (airo#901). Reasons are logged for telemetry only, not branched on for UX
   in v1.
4. **Schema vendoring.** Airo vendors `schemas/intent/v1/schema.json` at a
   pinned version; drift check = CI compares vendored hash vs this repo's
   released tag. Additive-only v1.x means minor updates are safe to lag.
5. **Version negotiation.** Airo declares its supported schema major on
   `load_pack`; mismatch → reject + deterministic search. Enables independent
   release cadence.
6. **Runtime provisioning.** `core_ai` provides LiteRT execution; the
   llama.cpp path ships inside edge-ffi (no Airo work). Airo picks backend
   per device capability via pack manifest metadata.
7. **Offline guarantee.** Airplane-mode demo is Airo-side acceptance
   (airo#904). No network calls exist anywhere in the resolve path — this
   repo asserts none in the engine; Airo asserts app-side.
8. **Profile features.** Airo's routine detector (airo#905/#907) consumes the
   `schemas/profile-features/v1` vector — reads the versioned contract, not
   internals.

## Non-Goals (this milestone)

Sports live-state intelligence, scene intelligence, voice ASR, cloud
inference, TokenMask constraint strategy implementation.

## Issue Mapping

| Issue | Covered by |
|-------|-----------|
| #2 Schema + Rust types | Components: `schemas/intent/v1`, edge-intent types, ADR versioning rule |
| #3 Dataset + fine-tune | Training & Data section |
| #4 Constrained decoding + fallback | Constraint strategy layers, Error handling, fuzz gate |
| #5 Eval harness + gate | Eval Gate section |
| #6 Confidence + threshold | Confidence section |
| #7 Pack export + latency | Packaging section |
| #8 edge-media + edge-profile | Components section |
