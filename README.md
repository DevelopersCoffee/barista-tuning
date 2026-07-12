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

Rows use the existing SFT shape, but the output is strict media action JSON:

```json
{"instruction":"Translate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.","input":"Show Hindi news","output":"{\"clarification_required\":false,\"confidence\":0.92,\"constraints\":{\"genre\":\"news\",\"language\":\"hi\",\"live\":true},\"intent\":\"search\",\"missing_fields\":[],\"tool\":\"media.search\"}"}
```

The model is trained to emit SDK tool calls, not conversational answers or media
metadata.

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

- [Prompt Enhancement and Local Context Augmentation](docs/use-cases/prompt-enhancement-local-context.md)
- [Indian Splitwise-Style Finance QA](docs/use-cases/indian-splitwise-finance-qa.md)
- [Federated Enterprise Search with Citations](docs/use-cases/federated-enterprise-search-citations.md)
- [Release-Aware YugabyteDB Text-to-SQL](docs/use-cases/release-aware-yugabyte-text-to-sql.md)
- [Edge Task-Specific SLMs](docs/use-cases/edge-task-specific-slm.md)
- [Java Sonar SLM and Developer Digital Twin](docs/use-cases/java-sonar-developer-twin.md)

## Design

- [Domain Intelligence Platform Design](docs/design/slm-training-sdk.md)

## Research Notes

- [Blueprints and Prompt Template Search for SLMs](docs/research/blueprints-and-template-search.md)
- [CRAFT Synthetic Dataset Generation](docs/research/craft-synthetic-dataset-generation.md)
- [Fine-Tuned SLMs for Code Review Accuracy](docs/research/nvidia-code-review-slm-finetuning.md)
