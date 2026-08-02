# Enterprise Knowledge Cloud Sweep Preparation

## Status

Prepared; external training has not been submitted.

## Observed MLX v4 failures

The first 20 held-out predictions were classified with overlapping categories:

| Category | Count |
|---|---:|
| Parse error | 13 |
| Schema invalid | 13 |
| Intent mismatch | 15 |
| Relationship mismatch | 16 |
| Tool-call mismatch | 5 |
| Citation mismatch | 4 |
| Abstention mismatch | 1 |
| Unsafe tool | 0 |
| Exact-action mismatch | 20 |

The result supports a capacity and data-volume experiment while preserving the
existing zero-unsafe requirement.

## Governed dataset

- Training rows: 2,000; 500 per intent.
- Held-in evaluation rows: 200; 50 per intent.
- Distinct inputs: 1,847 training and 200 evaluation.
- Blueprint instruction mode: enabled.
- Safety v2 correction rows: 1,000 training and 100 evaluation.
- Safety conditions: authorization boundary, unsupported tool, missing evidence,
  stale evidence, unverified evidence, and conflicting evidence.
- Both files pass the enterprise knowledge v1 validator against the approved catalog.

## Experiment matrix

| Variant | Model | LoRA rank | Epochs | Precision |
|---|---|---:|---:|---|
| `smollm2_1_7b` | `HuggingFaceTB/SmolLM2-1.7B-Instruct` | 16 | 2 | FP16 |
| `qwen2_5_1_5b` | `Qwen/Qwen2.5-1.5B-Instruct` | 16 | 2 | FP16 |
| `qwen2_5_1_5b_rank32` | `Qwen/Qwen2.5-1.5B-Instruct` | 32 | 3 | FP16 |

All variants use the same 2,000/200 dataset, full attention and MLP LoRA targets,
gradient checkpointing, and unchanged held-out release requirements.

## Remote execution

Transfer one directory from `build/training-jobs`, install the repository with the
`train` extra on an authorized CUDA worker, enter the job directory, verify every
hash in `job.json`, and execute:

```bash
slm train config.yaml
```

Collect `output/model` and run the normal enterprise prediction and scoring commands.
Do not qualify a candidate from training or held-in loss. No bundle contains cloud
credentials, provider configuration, model weights, or production customer data.
