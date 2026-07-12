# SLM Train, Eval, Publish

This repo is a bootstrap for small language model work:

1. Fine-tune a base causal language model with supervised examples.
2. Evaluate the produced artifact before release.
3. Publish the checked model folder to Hugging Face Hub.

The default path is config-driven and keeps training, evaluation, and publishing as separate commands.

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
models/                   local model outputs, ignored by git
reports/                  eval reports, ignored by git
src/slm_train_eval_publish/
tests/
```
