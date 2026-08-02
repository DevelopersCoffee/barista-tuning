from __future__ import annotations

from pathlib import Path
from typing import Any

from slm_train_eval_publish.config import DataConfig
from slm_train_eval_publish.dataset_validation import validate_sft_rows


def load_sft_datasets(config: DataConfig) -> tuple[Any, Any | None]:
    from datasets import DatasetDict, load_dataset

    if config.dataset_name:
        dataset = load_dataset(
            config.dataset_name,
            config.dataset_config,
        )
        if not isinstance(dataset, DatasetDict):
            raise ValueError("Expected a dataset with named splits")

        train = dataset[config.train_split]
        eval_dataset = dataset[config.eval_split] if config.eval_split in dataset else None
        validate_sft_rows(
            train,
            config.validation_profile,
            validation_context_path=config.validation_context_path,
        )
        if eval_dataset is not None:
            validate_sft_rows(
                eval_dataset,
                config.validation_profile,
                validation_context_path=config.validation_context_path,
            )
        return train, eval_dataset

    train = _load_local_dataset(config.train_path)
    eval_dataset = _load_local_dataset(config.eval_path) if config.eval_path else None
    validate_sft_rows(
        train,
        config.validation_profile,
        validation_context_path=config.validation_context_path,
    )
    if eval_dataset is not None:
        validate_sft_rows(
            eval_dataset,
            config.validation_profile,
            validation_context_path=config.validation_context_path,
        )
    return train, eval_dataset


def format_sft_example(example: dict[str, Any], config: DataConfig) -> str:
    prompt, output = format_sft_prompt_and_output(example, config)
    return f"{prompt}{output}"


def format_sft_prompt_and_output(
    example: dict[str, Any], config: DataConfig
) -> tuple[str, str]:
    if config.text_field:
        text = example.get(config.text_field)
        if not text:
            raise ValueError(f"Missing configured text field '{config.text_field}'")
        return "", str(text)

    instruction = str(example.get(config.instruction_field, "")).strip()
    input_text = str(example.get(config.input_field, "")).strip()
    output = str(example.get(config.output_field, "")).strip()

    if not instruction or not output:
        raise ValueError("Each SFT row needs non-empty instruction and output values")

    if input_text:
        prompt = (
            "### Instruction\n"
            f"{instruction}\n\n"
            "### Input\n"
            f"{input_text}\n\n"
            "### Response\n"
        )
        return prompt, output

    prompt = (
        "### Instruction\n"
        f"{instruction}\n\n"
        "### Response\n"
    )
    return prompt, output


def _load_local_dataset(path: str | None) -> Any:
    from datasets import load_dataset

    if not path:
        raise ValueError("Local dataset path is required")

    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    suffix = dataset_path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        return load_dataset("json", data_files=str(dataset_path), split="train")
    if suffix == ".csv":
        return load_dataset("csv", data_files=str(dataset_path), split="train")

    raise ValueError(f"Unsupported dataset extension '{suffix}'. Use json, jsonl, or csv.")
