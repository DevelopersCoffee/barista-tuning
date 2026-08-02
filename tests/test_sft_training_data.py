from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from slm_train_eval_publish.config import DataConfig, ModelConfig, PipelineConfig
from slm_train_eval_publish.data import format_sft_example, format_sft_prompt_and_output
from slm_train_eval_publish.dataset_validation import validate_sft_rows
from slm_train_eval_publish.train import _enable_input_grads_for_checkpointing, _tokenize_dataset


class TinyDataset:
    column_names = ["instruction", "input", "output"]

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    def map(self, fn, remove_columns):  # type: ignore[no-untyped-def]
        return [fn(row) for row in self.rows]


class WhitespaceTokenizer:
    eos_token = "<eos>"
    eos_token_id = 0
    pad_token_id = 0

    def __call__(
        self,
        text: str,
        *,
        truncation: bool,
        max_length: int,
        padding: bool,
    ) -> dict[str, list[int]]:
        del truncation, padding
        tokens = text.split()[:max_length]
        return {
            "input_ids": list(range(1, len(tokens) + 1)),
            "attention_mask": [1] * len(tokens),
        }


class FakeModel:
    def __init__(self) -> None:
        self.enabled = False

    def enable_input_require_grads(self) -> None:
        self.enabled = True


def test_format_sft_prompt_and_output_separates_completion() -> None:
    row = {
        "instruction": "Return JSON only.",
        "input": "Show Hindi news",
        "output": '{"intent":"search"}',
    }

    prompt, output = format_sft_prompt_and_output(row, DataConfig(train_path="train.jsonl"))

    assert prompt.endswith("### Response\n")
    assert "Show Hindi news" in prompt
    assert output == '{"intent":"search"}'
    assert format_sft_example(row, DataConfig(train_path="train.jsonl")) == f"{prompt}{output}"


def test_tokenize_dataset_masks_prompt_labels() -> None:
    row = {
        "instruction": "Return JSON only.",
        "input": "Show Hindi news",
        "output": '{"intent":"search"}',
    }
    config = PipelineConfig(
        model=ModelConfig(base_model="tiny"),
        data=DataConfig(train_path="train.jsonl"),
    )
    config = replace(config, data=replace(config.data, max_seq_length=128))

    tokenized = _tokenize_dataset(TinyDataset([row]), WhitespaceTokenizer(), config)[0]

    prompt, _ = format_sft_prompt_and_output(row, config.data)
    prompt_token_count = len(prompt.split())
    assert tokenized["labels"][:prompt_token_count] == [-100] * prompt_token_count
    assert tokenized["labels"][prompt_token_count:] == tokenized["input_ids"][
        prompt_token_count:
    ]


def test_gradient_checkpointing_enables_input_grads_for_lora() -> None:
    config = PipelineConfig(
        model=ModelConfig(base_model="tiny"),
        data=DataConfig(train_path="train.jsonl"),
    )
    model = FakeModel()

    _enable_input_grads_for_checkpointing(model, config)

    assert model.enabled is True


def test_enterprise_validation_profile_rejects_invalid_output() -> None:
    rows = [
        {
            "instruction": "Return enterprise knowledge action JSON only.",
            "input": "Run a production update.",
            "output": '{"intent":"execute_sql"}',
        }
    ]

    try:
        validate_sft_rows(rows, "enterprise_knowledge_v1")
    except ValueError as error:
        assert "row 1" in str(error)
    else:
        raise AssertionError("enterprise validation should reject invalid output")


def test_enterprise_validation_profile_rejects_tool_outside_catalog() -> None:
    catalog_path = Path("examples/enterprise_knowledge/metadata_catalog.json")
    action = {
        "schema_version": "1.0",
        "intent": "live_data_lookup",
        "entities": [],
        "relationship_types": [],
        "requires_live_data": True,
        "evidence_policy": {
            "minimum_status": "verified",
            "citations_required": True,
        },
        "tool_call": {
            "tool": "unregistered_read_tool",
            "arguments": {"case_id": "CASE-REFERENCE"},
            "purpose": "case_explanation",
            "mode": "read_only",
        },
        "answer": None,
        "citations": [],
        "abstain": False,
        "reason": None,
    }
    rows = [
        {
            "instruction": "Return enterprise knowledge action JSON only.",
            "input": "Get a live case summary.",
            "output": json.dumps(action),
        }
    ]

    with pytest.raises(ValueError, match="approved tool catalog"):
        validate_sft_rows(
            rows,
            "enterprise_knowledge_v1",
            validation_context_path=catalog_path,
        )
