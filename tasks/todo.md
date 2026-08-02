# Enterprise Knowledge SLM Training Tasks

## Task 1: Define contract tests

**Acceptance criteria:**

- [x] Tests specify valid catalog and action behavior.
- [x] Tests cover unsafe tools, broken references, and inconsistent outputs.
- [x] Tests fail before implementation.

**Verification:**

- [x] `pytest tests/test_enterprise_knowledge.py tests/test_config.py`

**Dependencies:** None

**Files likely touched:**

- `tests/test_enterprise_knowledge.py`
- `tests/test_config.py`

## Task 2: Implement catalog and dataset compilation

**Acceptance criteria:**

- [x] Generic metadata catalog validates at the ingestion boundary.
- [x] All four intent families generate strict action envelopes.
- [x] Train and evaluation splits are deterministic.

**Verification:**

- [x] `pytest tests/test_enterprise_knowledge.py`

**Dependencies:** Task 1

**Files likely touched:**

- `src/slm_train_eval_publish/enterprise_knowledge.py`
- `examples/enterprise_knowledge/metadata_catalog.json`

## Task 3: Enforce the training validation profile

**Acceptance criteria:**

- [x] `DataConfig` accepts an optional validation profile.
- [x] Enterprise knowledge rows are validated before training.
- [x] Existing configurations keep their previous behavior.

**Verification:**

- [x] `pytest tests/test_sft_training_data.py tests/test_config.py`

**Dependencies:** Task 2

**Files likely touched:**

- `src/slm_train_eval_publish/config.py`
- `src/slm_train_eval_publish/data.py`
- `src/slm_train_eval_publish/dataset_validation.py`
- `tests/test_sft_training_data.py`
- `tests/test_config.py`

## Task 4: Add runnable use-case artifacts

**Acceptance criteria:**

- [x] CLI generates and validates enterprise knowledge JSONL.
- [x] Example DDL compiles.
- [x] Training config loads and targets generated paths.

**Verification:**

- [x] `slm compile examples/enterprise_knowledge/domain.yaml --output build`
- [x] Generate and validate smoke splits.

**Dependencies:** Tasks 2 and 3

**Files likely touched:**

- `src/slm_train_eval_publish/cli.py`
- `examples/enterprise_knowledge/domain.yaml`
- `configs/enterprise_knowledge_sft.yaml`

## Task 5: Document and review

**Acceptance criteria:**

- [x] README documents the end-to-end commands and links the use case.
- [x] Full tests and lint pass.
- [x] Five-axis review finds no unresolved required issue.

**Verification:**

- [x] `pytest`
- [x] `ruff check .`

**Dependencies:** Tasks 1–4

**Files likely touched:**

- `README.md`
- `tasks/todo.md`

## Task 15: Add blueprint instruction mode

**Acceptance criteria:**

- [x] `basic` remains the default and produces the current instruction.
- [x] `blueprint` includes catalog relationship and approved-tool definitions.
- [x] Unknown modes fail before writing data.

**Verification:**

- [x] Focused tests fail before implementation, then pass.

## Task 16: Train and evaluate context-matched adapter

**Acceptance criteria:**

- [x] Governed 64/16 blueprint splits validate.
- [x] Two-epoch query/value training completes through native MLX.
- [x] Blueprint inference receives an explicit unchanged requirements verdict.

**Verification:**

- [x] Full tests and lint pass.
- [x] Measured report is documented.

## Task 17: Add portable execution contracts

**Acceptance criteria:**

- [x] Existing configs default to the Transformers backend.
- [x] Unknown backends and invalid MLX options fail at config load.
- [x] Tests define MLX conversion, command, iteration, and platform behavior.

**Verification:**

- [x] New focused tests fail before implementation, then pass.

## Task 18: Implement MLX and portable job packaging

**Acceptance criteria:**

- [x] Apple Silicon can run the same SFT rows through `mlx_lm.lora`.
- [x] A portable directory includes rewritten config, required inputs, checksums,
  backend, and the exact run command.
- [x] No cloud SDK, credential, or Databricks dependency is introduced.

**Verification:**

- [x] CLI packaging smoke test passes.
- [x] Full tests and lint pass.

## Task 19: Analyze held-out model failures

**Acceptance criteria:**

- [x] Analysis reports multi-label failure categories and bounded examples.
- [x] Malformed and unsafe outputs are distinguished from semantic mismatches.
- [x] CLI writes a deterministic JSON report.

**Verification:**

- [x] Focused tests fail before implementation, then pass.

## Task 20: Prepare cloud quality sweep

**Acceptance criteria:**

- [x] The 2,000/200 blueprint dataset validates and is balanced by intent.
- [x] Three FP16 CUDA configs load against the same dataset.
- [x] Three portable bundles contain verified checksums and no credentials.

**Verification:**

- [x] Config, dataset, CLI, full-test, and lint checks pass.

## Task 6: Define evaluation contracts

**Acceptance criteria:**

- [x] Tests specify parsing, metric formulas, safety classification, and threshold
  verdicts.
- [x] Tests prove benchmark and training catalogs must be disjoint.
- [x] Tests fail before implementation.

**Verification:**

- [x] `pytest tests/test_enterprise_knowledge_evaluation.py`

**Dependencies:** Tasks 1–5

**Files likely touched:**

- `tests/test_enterprise_knowledge_evaluation.py`

## Task 7: Implement prediction and scoring

**Acceptance criteria:**

- [x] Prediction parsing preserves schema-invalid JSON for safety analysis.
- [x] Scoring reports all required quality and safety metrics.
- [x] Versioned thresholds produce per-metric and overall verdicts.

**Verification:**

- [x] `pytest tests/test_enterprise_knowledge_evaluation.py`

**Dependencies:** Task 6

**Files likely touched:**

- `src/slm_train_eval_publish/enterprise_knowledge_evaluation.py`
- `src/slm_train_eval_publish/structured_output.py`

## Task 8: Add held-out benchmark

**Acceptance criteria:**

- [x] Benchmark catalog IDs do not overlap training catalog IDs.
- [x] Generated benchmark has at least 100 rows and all four intents.
- [x] Every expected action validates against the benchmark tool catalog.

**Verification:**

- [x] Generate and validate `data/processed/enterprise_knowledge_benchmark.jsonl`.

**Dependencies:** Task 7

**Files likely touched:**

- `examples/enterprise_knowledge/benchmark_catalog.json`
- `examples/enterprise_knowledge/requirements.yaml`

## Task 9: Run the base-model benchmark

**Acceptance criteria:**

- [x] CLI predicts from a Hugging Face model ID or local model directory.
- [x] A real base-model smoke report is written.
- [x] The report clearly identifies every passed and failed requirement.

**Verification:**

- [x] Run prediction with `--limit 20`.
- [x] Score predictions against the same 20 expected rows.

**Dependencies:** Task 8

**Files likely touched:**

- `src/slm_train_eval_publish/cli.py`
- `reports/enterprise_knowledge_base_smoke_report.json`

## Task 10: Final quality gate

**Acceptance criteria:**

- [x] Full tests and lint pass.
- [x] Documentation includes exact commands and measured baseline status.
- [x] Five-axis review finds no unresolved required issue.

**Verification:**

- [x] `pytest`
- [x] `ruff check .`

**Dependencies:** Tasks 6–9

**Files likely touched:**

- `README.md`
- `docs/design/enterprise-knowledge-training.md`

## Task 11: Specify schema-correction examples

**Acceptance criteria:**

- [x] Tests require one correction-style example per four rows in every intent.
- [x] Tests require deterministic generation and valid action outputs.
- [x] Stronger configuration test requires all attention and MLP projections.

**Verification:**

- [x] New tests fail before implementation.

**Dependencies:** Tasks 1–10

**Files likely touched:**

- `tests/test_enterprise_knowledge.py`
- `tests/test_config.py`

## Task 12: Implement schema-focused training inputs

**Acceptance criteria:**

- [x] Correction drafts are clearly marked untrusted and invalid.
- [x] Correction augmentation changes inputs but never creates invalid targets.
- [x] Benchmark generation remains free of training-only augmentation.

**Verification:**

- [x] `pytest tests/test_enterprise_knowledge.py tests/test_config.py`

**Dependencies:** Task 11

**Files likely touched:**

- `src/slm_train_eval_publish/enterprise_knowledge.py`
- `configs/enterprise_knowledge_schema_sft.yaml`

## Task 13: Train and evaluate stronger adapter

**Acceptance criteria:**

- [x] Schema-focused 256/64 splits validate.
- [x] Four-epoch adapter training completes locally.
- [x] Unchanged held-out benchmark produces an explicit requirements verdict.

**Verification:**

- [x] Score the adapter against up to all 100 disjoint cases.

**Dependencies:** Task 12

**Files likely touched:**

- `reports/enterprise_knowledge_schema_v2_report.json`

## Task 14: Record and review experiment

**Acceptance criteria:**

- [x] Measured report documents pass or failure without relaxing thresholds.
- [x] Full tests and lint pass.
- [x] Five-axis review has no unresolved required issue.

**Verification:**

- [x] `pytest`
- [x] `ruff check .`

**Dependencies:** Task 13

**Files likely touched:**

- `docs/evaluation/enterprise-knowledge-smoke-baseline.md`
- `tasks/plan.md`
- `tasks/todo.md`
