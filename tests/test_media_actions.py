from __future__ import annotations

import json
from pathlib import Path

from slm_train_eval_publish.media_actions import (
    SYSTEM_INSTRUCTION,
    generate_media_action_examples,
    write_media_actions_jsonl,
    write_media_actions_split,
)


def test_generate_media_action_examples_are_structured() -> None:
    examples = generate_media_action_examples(count=100, seed=7)

    assert len(examples) == 100
    assert {example.tool for example in examples} <= {
        "media.search",
        "media.play",
        "media.recommend",
        "media.resume",
        "media.browse",
        "media.favorite",
        "media.clarify",
    }

    row = examples[0].to_sft_row()
    assert row["instruction"] == SYSTEM_INSTRUCTION
    parsed = json.loads(row["output"])
    assert parsed["tool"].startswith("media.")
    assert isinstance(parsed["constraints"], dict)
    assert isinstance(parsed["clarification_required"], bool)
    assert any(example.utterance == "Sports in HD only" for example in examples)
    assert any(example.constraints.get("genre") == "business_news" for example in examples)
    assert any(example.constraints.get("subscription") == "free" for example in examples)


def test_write_media_actions_jsonl(tmp_path: Path) -> None:
    output = write_media_actions_jsonl(tmp_path / "actions.jsonl", count=10, seed=1)

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(rows) == 10
    assert set(rows[0]) == {"instruction", "input", "output"}

    action = json.loads(rows[0]["output"])
    assert set(action) == {
        "intent",
        "tool",
        "confidence",
        "constraints",
        "missing_fields",
        "clarification_required",
    }


def test_write_media_actions_split(tmp_path: Path) -> None:
    train, eval_ = write_media_actions_split(
        train_output=tmp_path / "train.jsonl",
        eval_output=tmp_path / "eval.jsonl",
        train_count=12,
        eval_count=4,
        seed=3,
    )

    train_rows = train.read_text().splitlines()
    eval_rows = eval_.read_text().splitlines()

    assert len(train_rows) == 12
    assert len(eval_rows) == 4
    assert train_rows[0] != eval_rows[0]
