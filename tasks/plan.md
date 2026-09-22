# Implementation Plan: Enterprise Knowledge SLM Training

## Overview

Add one end-to-end, generic training use case that compiles an enterprise knowledge
domain, validates a governed metadata catalog, generates safe structured SFT splits,
and uses the existing PEFT training pipeline with an enterprise-specific validation
profile.

## Architecture Decisions

- Train stable request-handling behavior; retrieve changing enterprise facts at runtime.
- Keep the existing `instruction`/`input`/`output` SFT interface and add an optional
  validation profile, preserving all current consumers.
- Use one versioned action envelope across intent families to simplify training and
  runtime validation.
- Keep Databricks behind the storage/publication boundary; add no cloud dependency.

## Dependency Graph

```text
metadata and action contracts
  -> failing contract tests
  -> catalog validator and deterministic generator
  -> dataset validation profile
  -> CLI and training config
  -> compiled example and documentation verification
```

## Task List

### Phase 1: Contract

- [x] Add failing tests for catalog validation, action validation, generation, and splits.
- [x] Add failing tests for the optional training-data validation profile.

### Checkpoint: Contract

- [x] New tests fail for missing behavior, while existing tests remain unchanged.

### Phase 2: Core implementation

- [x] Implement metadata catalog and enterprise action validation.
- [x] Implement deterministic example generation and JSONL split writing.
- [x] Integrate the validation profile into the generic dataset loading boundary.

### Checkpoint: Core

- [x] Targeted unit tests pass.
- [x] Existing SFT behavior remains backward compatible.

### Phase 3: Usable training path

- [x] Add the CLI generation and validation commands.
- [x] Add the example DDL, metadata catalog, and training configuration.
- [x] Document the commands and link the use case from the README.

### Checkpoint: Complete

- [x] Example DDL compiles.
- [x] Generated smoke splits validate.
- [x] Full Python tests and lint pass.
- [x] Five-axis review has no unresolved required findings.

## Phase 4: Context-Matched Blueprint Training

- [x] Define backward-compatible instruction-mode contracts.
- [x] Implement blueprint split generation through the CLI.
- [x] Generate and validate context-matched splits.
- [x] Train a two-epoch local query/value adapter.
- [x] Evaluate with the unchanged blueprint benchmark path.
- [x] Record the local execution blocker and complete quality review.

## Phase 5: Portable Training Backends

- [x] Define the additive backend and portable-job contracts with failing tests.
- [x] Dispatch the existing trainer through an explicit Transformers backend.
- [x] Add native MLX dataset preparation and LoRA command execution for Apple Silicon.
- [x] Add a provider-neutral training-job packager and CLI command.
- [x] Add an MLX context-training configuration and operator documentation.
- [x] Run full tests, lint, CLI smoke checks, and the five-axis review.

## Phase 6: Cloud Quality Sweep

- [x] Define error-analysis and FP16 configuration contracts with failing tests.
- [x] Implement deterministic prediction error analysis and CLI reporting.
- [x] Generate and validate balanced 2,000/200 blueprint data.
- [x] Add three 1.5B–1.7B CUDA experiment configurations.
- [x] Package and checksum all three provider-neutral jobs.
- [x] Run full tests, lint, data audits, and the five-axis review.

## Phase 7: Code Index Ingestion

- [x] Define the vendor-neutral Code Index Export v1 contract and ADR.
- [x] Add failing validation and deterministic compilation tests.
- [x] Implement the export validator and metadata-catalog compiler.
- [x] Expose `slm compile-code-index` with a generic example export.
- [x] Run full tests, lint, deterministic rebuild, and five-axis review.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Mutable facts leak into weights | Incorrect or stale answers | Train behavior from generic facts and retrieve current facts at runtime |
| Extracted metadata is malformed | Unsafe training targets | Strict catalog boundary validation and reference checks |
| Model learns unsafe execution | Production security exposure | Read-only tool schema and rejection of arbitrary execution |
| Mixed task outputs confuse a small model | Low structured accuracy | One action envelope and task-specific evaluation families |
| Framework compatibility breaks | Existing training jobs fail | Optional additive validation profile with unchanged default |

## Open Questions

None for the local framework slice.

## Phase 2: Enterprise Knowledge Evaluation

### Architecture Decisions

- Use a separate held-out catalog so the benchmark tests behavioral generalization.
- Preserve invalid parsed objects for safety analysis while marking schema validity
  independently.
- Keep thresholds in a versioned YAML file rather than hard-coding release policy.
- Accept either a Hugging Face model ID or local adapter directory for prediction.

### Dependency Graph

```text
prediction and metric contracts
  -> failing unit tests
  -> parser and scorer
  -> held-out catalog and benchmark generator
  -> CLI prediction and scoring
  -> real base-model smoke run
  -> full quality review
```

### Task List

- [x] Define failing parser, metric, safety, isolation, and threshold tests.
- [x] Implement enterprise prediction parsing and deterministic scoring.
- [x] Add held-out catalog, requirements, and 100-row benchmark generation.
- [x] Add prediction and scoring CLI commands.
- [x] Install existing training extras and run a real base-model smoke benchmark.
- [x] Record the report and update documentation with the measured verdict.

### Completion Checkpoint

- [x] Targeted and full tests pass.
- [x] Full lint passes.
- [x] Benchmark isolation and coverage checks pass.
- [x] Base-model smoke report contains all required metrics and requirement verdicts.
- [x] Five-axis review has no unresolved required findings.

## Phase 3: Schema-Focused Adaptation

### Architecture Decisions

- Preserve the 360M base model to isolate training-strategy effects.
- Add deterministic correction inputs only to train/evaluation split generation;
  held-out benchmark generation remains unchanged.
- Expand LoRA across attention and MLP projections for schema-learning capacity.
- Keep the existing benchmark and release requirements immutable.

### Dependency Graph

```text
correction-example contract
  -> failing generation/config tests
  -> deterministic correction augmentation
  -> stronger LoRA config and governed splits
  -> local training
  -> unchanged held-out evaluation
  -> measured report and quality review
```

### Task List

- [x] Define correction-example and stronger-config tests.
- [x] Implement balanced deterministic correction augmentation.
- [x] Generate and validate schema-focused train/evaluation splits.
- [x] Train the stronger adapter.
- [x] Score it against the unchanged held-out benchmark.
- [x] Record the measured verdict and complete the quality review.

### Completion Checkpoint

- [x] Targeted and full tests pass.
- [x] Full lint passes.
- [x] Generated correction examples are balanced and schema-valid.
- [x] The real adapter report contains all metrics and requirement verdicts.
- [x] Five-axis review has no unresolved required findings.
