# Enterprise Knowledge SLM Training Support

## Objective

Extend the existing SLM training framework with a reproducible use-case pipeline
for offline enterprise knowledge extraction. The pipeline must turn a governed
metadata catalog into deterministic supervised fine-tuning (SFT) splits that teach
an SLM to:

- classify enterprise knowledge requests
- plan constrained semantic metadata retrieval
- synthesize answers only from authorized evidence
- route live-data requests to allowlisted read-only tools
- abstain when evidence is missing, stale, conflicting, or unauthorized

Enterprise facts and production data remain external to model weights.

## Assumptions

1. The generic training pipeline and JSONL SFT shape remain backward compatible.
2. Databricks is a publication and serving target, not a Python runtime dependency.
3. Phase 1 uses a checked-in, generic metadata catalog fixture; real offline
   extractors can emit the same contract later.
4. Model training itself may require external model downloads and accelerator
   resources, so local completion is proven by deterministic dataset generation,
   validation, config loading, and automated tests.
5. Only read-only runtime tools are valid training targets for this use case.

## Contract

### Metadata catalog input

The catalog contains:

- `knowledge_release`
- `entities`
- `relationships`
- `evidence`
- `approved_tools`

Every entity and relationship has stable identifiers and provenance. Relationships
reference known entities and evidence. Approved tools declare `mode: read_only`.

### SFT row

The existing additive SFT contract is retained:

```json
{
  "instruction": "Return enterprise knowledge action JSON only.",
  "input": "Which service calculates the obligation ratio?",
  "output": "{\"schema_version\":\"1.0\",...}"
}
```

### Enterprise knowledge action

Every output uses one strict, versioned shape:

```json
{
  "schema_version": "1.0",
  "intent": "metadata_lookup",
  "entities": [
    {
      "type": "business_concept",
      "query": "obligation ratio"
    }
  ],
  "relationship_types": [
    "COMPUTES",
    "OWNED_BY",
    "EVIDENCED_BY"
  ],
  "requires_live_data": false,
  "evidence_policy": {
    "minimum_status": "verified",
    "citations_required": true
  },
  "tool_call": null,
  "answer": null,
  "citations": [],
  "abstain": false,
  "reason": null
}
```

Supported intents:

- `metadata_lookup`
- `grounded_answer`
- `live_data_lookup`
- `abstain`

The validator rejects unknown fields, unknown relationship types, unsafe tools,
missing citations for grounded answers, and inconsistent abstention or live-data
states.

## Commands

```bash
slm compile examples/enterprise_knowledge/domain.yaml --output build
slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json \
  --train-count 5000 \
  --eval-count 500
slm validate-enterprise-knowledge-data \
  data/processed/enterprise_knowledge_train.jsonl
slm train configs/enterprise_knowledge_sft.yaml
pytest tests/test_enterprise_knowledge.py tests/test_config.py
pytest
ruff check .
```

## Project Structure

```text
examples/enterprise_knowledge/
  domain.yaml                 Domain Definition Language source
  metadata_catalog.json       Generic governed metadata fixture
configs/
  enterprise_knowledge_sft.yaml
src/slm_train_eval_publish/
  enterprise_knowledge.py     catalog validation and dataset generation
  dataset_validation.py       training-boundary validation profiles
tests/
  test_enterprise_knowledge.py
docs/use-cases/
  offline-enterprise-knowledge-extraction.md
```

## Code Style

Use frozen dataclasses for immutable example records, deterministic `random.Random`
instances, `Path` for filesystem boundaries, and compact sorted JSON outputs:

```python
return {
    "instruction": SYSTEM_INSTRUCTION,
    "input": self.user_input,
    "output": json.dumps(self.action, sort_keys=True, separators=(",", ":")),
}
```

## Testing Strategy

- Unit-test catalog and action validation as pure functions.
- Prove deterministic generation and disjoint random streams for train/eval splits.
- Test unsafe write tools, unknown references, malformed output, and missing citations.
- Test the CLI-relevant JSONL writer through its public function.
- Test that the training config opts into the enterprise validation profile.
- Run the complete Python suite and linter after targeted tests pass.

## Boundaries

### Always

- Validate offline extraction output as untrusted input.
- Require provenance, stable identifiers, evidence, and knowledge release.
- Generate only schema-valid outputs.
- Keep all tool targets read-only.
- Preserve the existing SFT configuration defaults.

### Ask first

- Add a live Databricks connection.
- Add credentials, cloud resources, or a new dependency.
- Change the generic SFT prompt format.
- Add production data or proprietary source code.

### Never

- Put secrets, customer records, or production payloads in fixtures or training data.
- Train arbitrary SQL, shell, URL, or source-code execution.
- Treat embeddings or inferred summaries as the canonical source of truth.
- Silently accept stale, conflicting, or unauthorized evidence.

## Success Criteria

- The example domain compiles into the existing Domain IR and pack artifacts.
- The metadata fixture validates with stable entity, relationship, evidence, and tool
  references.
- Dataset generation emits deterministic, schema-valid train and evaluation JSONL.
- All four intent families are present in a representative generated dataset.
- The enterprise action validator rejects unsafe or internally inconsistent outputs.
- The training loader validates enterprise rows when the config profile is enabled.
- The provided config loads and points at the generated splits.
- Targeted tests, the complete test suite, and linting pass.

## Open Questions

None block Phase 1. A real Databricks publisher and graph-serving projection remain
separate deployment integrations because they require environment-specific
authorization, catalog naming, and infrastructure decisions.

## Evaluation Contract

The enterprise-knowledge adapter must be evaluated on a held-out catalog rather than
on paraphrases of training entities. Benchmark entity IDs, evidence IDs, and tool IDs
must be disjoint from the training catalog.

### Prediction record

Model prediction JSONL uses this boundary:

```json
{
  "input": "Which workflow handles a failed repayment event?",
  "output": {
    "schema_version": "1.0",
    "intent": "metadata_lookup"
  },
  "raw_completion": "{\"schema_version\":\"1.0\",...}",
  "parse_error": null
}
```

`output` preserves a parsed JSON object even when it is schema-invalid so the safety
scorer can detect write-capable, arbitrary, or unapproved actions. It is `null` only
when no JSON object can be parsed.

### Required metrics

| Metric | Meaning | Requirement |
|---|---|---|
| `schema_valid_rate` | Predictions satisfying Enterprise Knowledge Action v1 | at least 0.98 |
| `intent_accuracy` | Exact intent match | at least 0.90 |
| `relationship_exact_accuracy` | Exact set of requested relationship types | at least 0.85 |
| `tool_call_accuracy` | Exact approved tool call on live-data examples | at least 0.95 |
| `citation_coverage` | Grounded answers containing every required citation | at least 0.95 |
| `abstention_accuracy` | Correct abstention behavior | at least 0.90 |
| `exact_action_accuracy` | Exact full structured action | at least 0.75 |
| `unsupported_claim_rate` | Answers lacking required evidence or answering when they should not | at most 0.02 |
| `unsafe_action_rate` | Write, arbitrary, or unapproved action attempts | exactly 0.00 |

These are release requirements for a deployable adapter. A base-model baseline is
expected to miss some requirements; that result determines whether adaptation is
necessary.

### Commands

```bash
slm generate-enterprise-knowledge-benchmark \
  examples/enterprise_knowledge/benchmark_catalog.json \
  --training-catalog examples/enterprise_knowledge/metadata_catalog.json \
  --output data/processed/enterprise_knowledge_benchmark.jsonl \
  --count 100

slm predict-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  HuggingFaceTB/SmolLM2-360M-Instruct \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --prompt-mode blueprint \
  --output reports/enterprise_knowledge_base_predictions.jsonl

slm score-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  reports/enterprise_knowledge_base_predictions.jsonl \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --requirements examples/enterprise_knowledge/requirements.yaml \
  --output reports/enterprise_knowledge_base_report.json
```

For a bounded local smoke run, pass `--limit 20` to prediction. A full release
verdict must score the complete benchmark without a limit.

## Evaluation Success Criteria

- The benchmark contains at least 100 examples and all four intent families.
- Every benchmark row is unique and the four intent families are balanced.
- Training and benchmark catalogs have no overlapping entity, evidence, or tool IDs.
- Expected benchmark actions validate against the benchmark tool catalog.
- Prediction prompts never contain the expected output.
- Malformed model output is preserved and reported without crashing evaluation.
- Unsafe and unsupported outputs are measured independently from schema validity.
- Requirements are loaded from a versioned file and every configured check appears in
  the report with its actual value, threshold, operator, and verdict.
- A real base-model smoke report is produced before adapter training.

## Schema-Focused Adaptation Experiment

The initial one-epoch adapter reduced held-in loss but produced no schema-valid
held-out actions. The next bounded experiment changes learning capacity without
changing the model family, held-out catalog, action contract, or release thresholds.

### Objective

Determine whether `HuggingFaceTB/SmolLM2-360M-Instruct` can generalize the
Enterprise Knowledge Action v1 envelope after:

- four supervised epochs over 256 governed training rows
- LoRA coverage of all attention and MLP projections
- deterministic correction-style examples distributed across all four intents

Correction examples include an explicitly untrusted malformed draft in the input
and retain the same validated action as the output. They teach the model to reject
generic `status`, `result`, arbitrary-action, and evidence-shaped JSON without
adding invalid targets to the dataset.

### Boundaries

- Always validate every generated target before tokenization.
- Keep correction examples balanced across all four intent families.
- Treat malformed drafts as input data, never as executable instructions.
- Do not place benchmark catalog identifiers in training examples.
- Do not change `examples/enterprise_knowledge/requirements.yaml`.
- Do not qualify a model from training loss or held-in evaluation loss.

### Commands

```bash
slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json \
  --train-output data/processed/enterprise_knowledge_schema_train.jsonl \
  --eval-output data/processed/enterprise_knowledge_schema_eval.jsonl \
  --train-count 256 \
  --eval-count 64 \
  --seed 42

slm train configs/enterprise_knowledge_schema_sft.yaml

slm predict-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  models/enterprise-knowledge-smollm2-360m-schema-v2 \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --prompt-mode sft \
  --output reports/enterprise_knowledge_schema_v2_predictions.jsonl \
  --max-new-tokens 256

slm score-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  reports/enterprise_knowledge_schema_v2_predictions.jsonl \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --requirements examples/enterprise_knowledge/requirements.yaml \
  --output reports/enterprise_knowledge_schema_v2_report.json \
  --fail-on-requirements
```

### Success criteria

- Exactly one quarter of each generated intent family uses a correction-style input.
- Correction examples remain deterministic and their outputs pass the existing
  enterprise action validator.
- The stronger training configuration targets `q_proj`, `k_proj`, `v_proj`,
  `o_proj`, `gate_proj`, `up_proj`, and `down_proj`.
- The adapter is scored against the unchanged disjoint benchmark.
- The measured report is recorded whether the adapter passes or fails.

### Measured result

The four-epoch adapter completed with held-in evaluation loss 0.00843. On the
balanced first 20 held-out cases it achieved 80% schema validity, 85% intent
accuracy, 100% citation coverage, and 95% abstention accuracy. It failed the
release requirements because relationship accuracy was 40%, tool-call accuracy
was 0%, exact-action accuracy was 25%, and one unapproved tool selection produced
a 5% unsafe-action rate.

Four schema failures make the 98% full-benchmark schema threshold unreachable,
so evaluation stopped decisively after 20 cases. Supplying the full runtime
blueprint to this adapter reduced schema validity to 0%, demonstrating that
blueprint-shaped runtime context must also be represented during training.

## Context-Matched Blueprint Experiment

Split generation accepts an explicit instruction mode. `basic` preserves the
existing short instruction and remains the default. `blueprint` embeds the action
contract, catalog relationship types, and approved read-only tool definitions.

The context-matched adapter trains with `blueprint` and is evaluated with the
existing blueprint prediction mode. Expected answers and benchmark identifiers
never enter training prompts. The local experiment uses 64 stratified training
rows and 16 evaluation rows after the 256/64 run proved impractical on the current
accelerator. Success requires deterministic schema-valid splits, two local
training epochs, and an unchanged held-out requirements verdict.

### Local execution status

The 64/16 context-matched splits validate and cover every intent. All-projection
training could not complete on the current host: sustained MPS throughput degraded
past three minutes per optimizer step, while forced CPU execution did not complete
one step within two minutes. Those partial runs were stopped without producing an
adapter. The local retry therefore retains the complete blueprint but limits LoRA
to query and value projections, the attention path most relevant to context and
tool selection.

A native MLX retry completed 128 micro-batch iterations with 1.638M trainable
parameters, 2.62 GB peak memory, held-in validation loss 0.089, and no optimizer
stall. On the balanced first 20 held-out cases, it achieved 35% schema validity,
20% intent accuracy, 15% relationship accuracy, 0% tool-call accuracy, 0% citation
coverage, 90% abstention accuracy, 0% exact-action accuracy, and zero unsafe or
unsupported outputs. It fails the unchanged requirements. Thirteen schema failures
make the 98% full-benchmark threshold unreachable, so evaluation stopped decisively
after 20 cases. MLX resolves local execution efficiency; it does not make this
360M/data recipe release-ready.

## Portable Training Execution

### Objective

Run the same validated SFT contract on either Apple Silicon or a remote CUDA/CPU
worker without changing generated examples, release requirements, or evaluation.
The execution engine is selected in configuration; the cloud provider is not part
of the training contract.

### Interface

- `training.backend: transformers` uses the existing Transformers/PEFT trainer.
- `training.backend: mlx` prepares MLX completion JSONL and invokes `mlx_lm.lora`.
- `slm package-training-job CONFIG --output DIRECTORY` creates a relocatable job
  directory with rewritten relative paths, input checksums, and an exact run command.
- Both backends return the configured adapter output directory.

### Boundaries

- Preserve the current Transformers behavior when `backend` is omitted.
- Validate governed rows before converting them to a backend-specific format.
- Never include credentials, model caches, generated adapters, or provider SDK state
  in a portable job.
- Do not submit paid cloud work automatically. A person or deployment system chooses
  the remote runner after reviewing its quota and data controls.
- Reject MLX on hosts that are not Apple Silicon with an actionable error.
- Keep Databricks outside this architecture.

### Success criteria

- Existing configurations continue to load and train through Transformers.
- MLX command construction maps epochs to deterministic micro-batch iterations,
  masks prompt tokens, and preserves LoRA rank, scale, dropout, and target modules.
- A packaged job contains its config, local train/evaluation/validation inputs,
  SHA-256 checksums, backend, and `slm train config.yaml` command.
- Unit tests require neither a GPU nor MLX installation.
- Full tests and lint pass before a real MLX smoke run is attempted.

## Cloud Quality Sweep

### Objective

Determine whether model capacity and governed data volume—not the action contract—
are responsible for the context-matched release failure. Train three bounded LoRA
variants on the same 2,000/200 blueprint dataset and score every candidate against
the unchanged disjoint benchmark and requirements.

### Experiment contract

- Generate 2,000 training and 200 held-in evaluation rows with balanced intent
  families and deterministic schema-correction examples.
- Produce a machine-readable error analysis from the MLX v4 predictions before
  selecting the sweep.
- Compare SmolLM2 1.7B and Qwen2.5 1.5B at rank 16; use a rank-32 Qwen variant as
  the capacity ablation.
- Use the Transformers backend with FP16 and gradient checkpointing for CUDA workers.
- Package every variant with local inputs and SHA-256 checksums.
- Do not submit a paid job or copy data to an external provider automatically.

### Acceptance criteria

- Error analysis reports overlapping schema, intent, relationship, tool, citation,
  abstention, unsafe-tool, and parse-error categories with bounded examples.
- Generated data validates against the approved catalog and contains exactly 500
  targets for each intent in training and 50 for each intent in evaluation.
- All three configurations load, use the same data and release contract, and differ
  only in declared model/capacity settings.
- All three portable bundles verify locally before external transfer.
- A candidate is qualified only by the existing full held-out requirements; training
  loss and held-in loss are diagnostic signals, not release evidence.
