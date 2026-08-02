# Enterprise Knowledge SLM Smoke Baseline

## Verdict

Neither `HuggingFaceTB/SmolLM2-360M-Instruct` nor the bounded one-epoch LoRA
adapter satisfies the Enterprise Knowledge Action v1 requirements.

This is a decisive early-stop failure. The first 20 cases contain five examples
from each intent family and all 20 responses failed schema validation. Even if
the remaining 80 cases were perfect, full-benchmark schema validity could reach
only 80%, below the required 98%.

The result verifies that the training framework, governed dataset validation,
model prediction, structured parsing, held-out scoring, and requirement gates
work end to end. It does not qualify either evaluated model for deployment.

## Evaluation boundary

- Base model: `HuggingFaceTB/SmolLM2-360M-Instruct`
- Adapter: one epoch, 256 training rows, 64 held-in evaluation rows, LoRA on
  `q_proj` and `v_proj`
- Held-out benchmark: 100 unique rows, balanced across `metadata_lookup`,
  `grounded_answer`, `live_data_lookup`, and `abstain`
- Smoke slice: first 20 balanced rows
- Isolation: benchmark entity, evidence, and tool IDs are disjoint from training
  catalog IDs
- Decoding: deterministic greedy generation, maximum 256 new tokens

## Measured results

| Metric | Requirement | Base | Adapter |
|---|---:|---:|---:|
| Schema valid rate | >= 0.98 | 0.00 | 0.00 |
| Intent accuracy | >= 0.90 | 0.05 | 0.00 |
| Relationship exact accuracy | >= 0.85 | 0.00 | 0.00 |
| Tool-call accuracy | >= 0.95 | 0.00 | 0.00 |
| Citation coverage | >= 0.95 | 0.00 | 0.00 |
| Abstention accuracy | >= 0.90 | 0.05 | 0.00 |
| Exact-action accuracy | >= 0.75 | 0.00 | 0.00 |
| Unsupported-claim rate | <= 0.02 | 0.05 | 0.00 |
| Unsafe-action rate | <= 0.00 | 0.05 | 0.00 |

The adapter's training loss decreased from approximately 2.43 to 1.30 and its
held-in evaluation loss was 1.305. Those loss values did not translate into
held-out contract compliance. Generated responses used plausible but unrelated
JSON shapes such as `status`, `result`, and `read_only_tools` instead of the
required action envelope.

## Reproduction

```bash
slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json \
  --train-output data/processed/enterprise_knowledge_smoke_train.jsonl \
  --eval-output data/processed/enterprise_knowledge_smoke_eval.jsonl \
  --train-count 256 \
  --eval-count 64 \
  --seed 42

slm train configs/enterprise_knowledge_smoke_sft.yaml

slm predict-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  models/enterprise-knowledge-smollm2-360m-smoke \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --prompt-mode sft \
  --output reports/enterprise_knowledge_adapter_smoke_predictions.jsonl \
  --limit 20 \
  --max-new-tokens 256

slm score-enterprise-knowledge \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  reports/enterprise_knowledge_adapter_smoke_predictions.jsonl \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --requirements examples/enterprise_knowledge/requirements.yaml \
  --output reports/enterprise_knowledge_adapter_smoke_report.json \
  --limit 20
```

## Next training experiment

The schema-focused experiment described below completed. Do not relax the
release gates. Constrained JSON decoding can be evaluated as a runtime safety
layer, but it must not replace the semantic accuracy requirements.

## Schema-focused adapter result

A second adapter trained for four epochs over the same 256/64 row boundary,
targeting all attention and MLP projections. One quarter of every intent family
used correction-style inputs containing clearly marked, untrusted malformed
drafts.

Training completed in approximately 39 minutes. Final held-in evaluation loss
was 0.00843, compared with 1.305 for the one-epoch adapter.

### Held-out smoke comparison

| Metric | Requirement | Base | One-epoch adapter | Schema v2 |
|---|---:|---:|---:|---:|
| Schema valid rate | >= 0.98 | 0.00 | 0.00 | 0.80 |
| Intent accuracy | >= 0.90 | 0.05 | 0.00 | 0.85 |
| Relationship exact accuracy | >= 0.85 | 0.00 | 0.00 | 0.40 |
| Tool-call accuracy | >= 0.95 | 0.00 | 0.00 | 0.00 |
| Citation coverage | >= 0.95 | 0.00 | 0.00 | 1.00 |
| Abstention accuracy | >= 0.90 | 0.05 | 0.00 | 0.95 |
| Exact-action accuracy | >= 0.75 | 0.00 | 0.00 | 0.25 |
| Unsupported-claim rate | <= 0.02 | 0.05 | 0.00 | 0.00 |
| Unsafe-action rate | <= 0.00 | 0.05 | 0.00 | 0.05 |

The result is a decisive failure on the balanced first 20 cases. Four invalid
schemas cap possible full-benchmark schema validity at 96%, below the required
98%, even if all remaining 80 cases were correct. One unapproved tool selection
also makes the zero-unsafe requirement unreachable.

The strongest gains are schema generation, citation behavior, and abstention.
The principal remaining gap is tool grounding: the short SFT prompt does not
supply disjoint benchmark tool definitions at runtime. Supplying the existing
full blueprint to the adapter caused instruction-distribution mismatch and
reduced schema validity to 0%.

The next experiment should train on the same catalog-supplied blueprint used at
inference, with tool definitions represented as runtime context rather than
facts to memorize. It should also add relationship-selection examples and use
constrained decoding for syntactic JSON validity. The unchanged benchmark and
requirements remain the acceptance boundary.
