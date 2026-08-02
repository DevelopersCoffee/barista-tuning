# SLM Train, Eval, Publish

This repo is a bootstrap for small language model work:

1. Fine-tune a base causal language model with supervised examples.
2. Evaluate the produced artifact before release.
3. Publish the checked model folder to Hugging Face Hub.

The default path is config-driven and keeps training, evaluation, and publishing as separate commands.

## Edge Intelligence Platform

The repo now also contains the Milestone 1 foundation for an Edge Intelligence
Platform:

> Edge Intelligence is a compiler and runtime for deploying domain-specific
> intelligence entirely on edge devices through immutable knowledge packs,
> deterministic execution, and interchangeable AI backends.

The Rust workspace is organized so the kernel remains domain-neutral:

```text
crates/edge-kernel      boring lifecycle, events, context, errors, diagnostics
crates/edge-pack        immutable ZIP pack contracts and lifecycle
crates/edge-storage     storage abstractions
crates/edge-search      retrieval and ranking contracts
crates/edge-intent      intent backend contract
crates/edge-profile     local profile signals
crates/edge-runtime     planner/domain service contracts
crates/edge-compiler    ingestion/transformation/compilation contracts
crates/edge-media       first domain package
crates/edge-cli         compiler/runtime CLI skeleton
bindings/flutter        thin Flutter FFI boundary notes
schemas/                versioned public schemas
docs/adr/               architecture decision records
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[all]"
```

For gated Hugging Face models or publishing:

```bash
cp .env.example .env
huggingface-cli login
```

## Data Format

The default config expects JSONL rows with these fields:

```json
{"instruction": "Write a short refund policy.", "input": "", "output": "Customers can request a refund within 30 days..."}
```

Place local data under `data/raw/`. Large datasets and model artifacts are ignored by git.

Current local sample source:

```text
data/raw/Zomato_Menu_Scraped.xlsx
```

It contains scraped restaurant menu rows with `Restaurant_Name`, `Category`, `Item_Name`, and `Price`, intended as the source data for menu question answering experiments.

## Train

```bash
slm train configs/sft.yaml
```

This writes adapter or model artifacts to the configured `training.output_dir`.

The default `training.backend` is `transformers`, which is appropriate for CUDA
cloud workers and remains backward compatible. On Apple Silicon, install the MLX
extra and select `backend: mlx`:

```bash
pip install -e ".[mlx]"
slm train configs/enterprise_knowledge_context_mlx_sft.yaml
```

To move the same local inputs to Colab, Hugging Face, GCP, or another controlled
runner, create a provider-neutral job directory:

```bash
slm package-training-job \
  configs/enterprise_knowledge_context_sft.yaml \
  --output build/training-jobs/enterprise-context-cuda
```

Upload that directory, install this package with the appropriate `train` or `mlx`
extra, verify the SHA-256 values in `job.json`, and run the manifest command from
the job directory. Packaging never submits a cloud job or includes credentials.
Enterprise prediction uses `--backend auto` by default and recognizes either a
PEFT adapter or an MLX adapter, so both paths feed the same scorer.

The cloud quality sweep uses a larger, safety-augmented blueprint dataset and three
bounded CUDA variants:

```bash
slm analyze-enterprise-knowledge-errors \
  data/processed/enterprise_knowledge_benchmark.jsonl \
  reports/enterprise_knowledge_context_mlx_v4_predictions.jsonl \
  --catalog examples/enterprise_knowledge/benchmark_catalog.json \
  --limit 20 \
  --output reports/enterprise_knowledge_context_mlx_v4_error_analysis.json

slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json \
  --train-output data/processed/enterprise_knowledge_cloud_train.jsonl \
  --eval-output data/processed/enterprise_knowledge_cloud_eval.jsonl \
  --train-count 2000 \
  --eval-count 200 \
  --seed 20260802 \
  --instruction-mode blueprint \
  --augmentation-profile safety_v2
```

Ready configurations are provided for SmolLM2 1.7B rank 16, Qwen2.5 1.5B rank
16, and Qwen2.5 1.5B rank 32. Package any configuration using the same command
shown above; cloud submission remains an explicit operator action. The measured
failure breakdown and experiment matrix are recorded in the
[cloud sweep preparation report](docs/evaluation/enterprise-knowledge-cloud-sweep-preparation.md).

## Airo TV Media Actions Dataset

Generate FunctionGemma-style SFT examples for Airo TV media actions:

```bash
slm generate-media-actions --output data/processed/airo_media_actions_train.jsonl --count 5000
```

For training, generate deterministic train/eval splits:

```bash
slm generate-media-action-splits --train-count 5000 --eval-count 500
```

Evaluate the local rule-baseline intent parser before model training:

```bash
slm eval-media-actions data/processed/airo_media_actions_eval.jsonl \
  --output reports/airo_media_actions_rule_eval.json
```

After a model produces JSONL predictions with `input` and `output` fields,
compare its exact tool-call accuracy against the rule baseline:

```bash
slm predict-media-actions \
  data/processed/airo_media_actions_eval.jsonl \
  models/airo-media-actions-smollm2-135m \
  --output reports/airo_media_actions_slm_predictions.jsonl

slm compare-media-action-predictions \
  data/processed/airo_media_actions_eval.jsonl \
  reports/airo_media_actions_slm_predictions.jsonl \
  --output reports/airo_media_actions_rule_vs_slm.json
```

Rows use the existing SFT shape, but the output is strict media action JSON:

```json
{"instruction":"Translate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.","input":"Show Hindi news","output":"{\"clarification_required\":false,\"confidence\":0.92,\"constraints\":{\"genre\":\"news\",\"language\":\"hi\",\"live\":true},\"intent\":\"search\",\"missing_fields\":[],\"tool\":\"media.search\"}"}
```

The model is trained to emit SDK tool calls, not conversational answers or media
metadata.
The trainer masks prompt tokens and optimizes only the JSON response span.
Prediction reports reject malformed or wrong-schema JSON before scoring exact
intent, tool, and constraint accuracy.

For a quick local adapter smoke run, generate the small split and train:

```bash
slm generate-media-action-splits \
  --train-output data/processed/airo_media_actions_smoke_train.jsonl \
  --eval-output data/processed/airo_media_actions_smoke_eval.jsonl \
  --train-count 24 \
  --eval-count 8

slm train configs/airo_media_actions_smoke_sft.yaml
```

At runtime, Rust FFI selects the local SLM backend by configuration. The Flutter
SDK API remains unchanged:

```bash
EDGE_INTELLIGENCE_INTENT_BACKEND=llama.cpp \
EDGE_INTELLIGENCE_LLAMA_CPP_BIN=/absolute/path/to/llama-completion \
EDGE_INTELLIGENCE_INTENT_MODEL=/absolute/path/to/base-model.gguf \
EDGE_INTELLIGENCE_INTENT_LORA=/absolute/path/to/airo-media-actions-lora.gguf
```

`EDGE_INTELLIGENCE_INTENT_LORA` is optional. Without these variables, the
runtime uses the production rule backend.
Set `EDGE_INTELLIGENCE_INTENT_BACKEND=llama.cpp+rule` to try llama.cpp first and
fall back to the Rust rule backend when the local model is unavailable or emits
an invalid/low-confidence intent.
Use `llama-completion` with `-no-cnv` for raw completion mode; `llama-cli` chat
mode can wrap the prompt and produce malformed schema output.

The Airo media-action model can be bundled, tested, and published with Make:

```bash
make airo-slm-predict PYTHON=/tmp/slm-train-venv/bin/python
make airo-slm-compare PYTHON=/tmp/slm-train-venv/bin/python
make airo-hf-test-llama
make airo-hf-publish \
  PYTHON=/tmp/slm-train-venv/bin/python \
  HF_REPO=developerscoffee/airo-media-actions-smollm2-135m
```

`make airo-hf-bundle` writes the Hugging Face upload payload under
`.cache/hf-publish/airo-media-actions-smollm2-135m`.

## Enterprise Knowledge SLM

The enterprise-knowledge use case teaches an SLM stable request-handling behavior
over an offline semantic metadata layer. It does not train changing enterprise facts
or production data into model weights.

The supplied generic catalog models business concepts, capabilities, services, APIs,
workflows, rules, policies, events, evidence, and approved read-only runtime tools.
Compile its domain definition first:

```bash
slm compile examples/enterprise_knowledge/domain.yaml --output build
```

Generate deterministic training and evaluation splits:

```bash
slm generate-enterprise-knowledge-splits \
  examples/enterprise_knowledge/metadata_catalog.json \
  --train-count 5000 \
  --eval-count 500
```

Every output uses a strict Enterprise Knowledge Action v1 JSON envelope. The dataset
contains four behavior families:

- constrained metadata retrieval planning
- grounded answers with citations
- approved read-only live-data tool routing
- abstention when verified and authorized evidence is unavailable

Validate generated or externally prepared rows before training:

```bash
slm validate-enterprise-knowledge-data \
  data/processed/enterprise_knowledge_train.jsonl
```

Train through the default Transformers/PEFT pipeline:

```bash
slm train configs/enterprise_knowledge_sft.yaml
```

The configuration enables the `enterprise_knowledge_v1` validation profile, so
malformed, unsafe, or internally inconsistent action outputs fail before tokenization
and training. The training and portable-job paths have no Databricks dependency.

Generate the disjoint, balanced held-out benchmark and evaluate a base model or
local adapter against versioned release requirements:

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
  --output reports/enterprise_knowledge_base_report.json \
  --fail-on-requirements
```

The scorer reports schema, intent, relationship, tool-call, citation, abstention,
exact-action, unsupported-claim, and unsafe-action metrics. A local smoke evaluation
of the unadapted 360M model and a one-epoch LoRA adapter found that neither learned
the required action schema. A four-epoch schema-focused adapter improved held-out
schema validity to 80% but still failed relationship, tool-grounding, exact-action,
and zero-unsafe release gates; see the
[measured baseline](docs/evaluation/enterprise-knowledge-smoke-baseline.md).

## IPTV To Media IR

Compile the current IPTV channel JSON or an M3U path/URL into Media IR v1:

```bash
slm compile-iptv /Users/udaychauhan/Downloads/current/iptv_channels.json \
  --output build/iptv-media-ir

slm compile-iptv https://iptv-org.github.io/iptv/index.m3u \
  --output build/iptv-media-ir
```

This emits:

```text
build/iptv-media-ir/media_ir.jsonl
build/iptv-media-ir/compile-report.json
```

Then compile the Media IR into a ZIP-based `.pack`:

```bash
slm compile-media-pack build/iptv-media-ir/media_ir.jsonl \
  --compile-report build/iptv-media-ir/compile-report.json \
  --output packs/media.iptv.india-0.1.0.pack
```

Or compile IPTV directly into a pack:

```bash
slm compile-iptv-pack https://iptv-org.github.io/iptv/index.m3u \
  --output packs/media.iptv.global-0.1.0.pack \
  --pack-id media.iptv.global \
  --pack-name "Global IPTV"
```

Validate the pack before bundling or installing it:

```bash
slm validate-media-pack packs/media.iptv.global-0.1.0.pack
```

Validation checks the manifest, checksum, required indexes/reports, `media.db`
tables, playable asset count, and asset-count consistency.

## Evaluate

```bash
slm evaluate configs/sft.yaml
```

Evaluation writes metrics and sample generations under `reports/`.

## Publish

```bash
slm publish configs/sft.yaml
```

Publishing uploads the configured model folder to `publish.repo_id`. Keep this disabled until the eval report is acceptable.

## Lightweight Development Checks

For config and package checks without installing the full ML stack:

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Project Layout

```text
configs/                  YAML configs for train/eval/publish runs
data/raw/                 local source data, ignored by git
data/processed/           derived data, ignored by git
docs/use-cases/           documented SLM use cases
models/                   local model outputs, ignored by git
reports/                  eval reports, ignored by git
src/slm_train_eval_publish/
tests/
```

## Use Cases

- [Offline Enterprise Knowledge Extraction for Grounded SLMs](docs/use-cases/offline-enterprise-knowledge-extraction.md)
- [Prompt Enhancement and Local Context Augmentation](docs/use-cases/prompt-enhancement-local-context.md)
- [Indian Splitwise-Style Finance QA](docs/use-cases/indian-splitwise-finance-qa.md)
- [Federated Enterprise Search with Citations](docs/use-cases/federated-enterprise-search-citations.md)
- [Release-Aware YugabyteDB Text-to-SQL](docs/use-cases/release-aware-yugabyte-text-to-sql.md)
- [Edge Task-Specific SLMs](docs/use-cases/edge-task-specific-slm.md)
- [Java Sonar SLM and Developer Digital Twin](docs/use-cases/java-sonar-developer-twin.md)

## Design

- [Domain Intelligence Platform Design](docs/design/slm-training-sdk.md)
- [Enterprise Knowledge SLM Training Support](docs/design/enterprise-knowledge-training.md)

## Research Notes

- [Blueprints and Prompt Template Search for SLMs](docs/research/blueprints-and-template-search.md)
- [CRAFT Synthetic Dataset Generation](docs/research/craft-synthetic-dataset-generation.md)
- [Fine-Tuned SLMs for Code Review Accuracy](docs/research/nvidia-code-review-slm-finetuning.md)
