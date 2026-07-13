from __future__ import annotations

import json
from pathlib import Path

from slm_train_eval_publish.media_actions import write_media_actions_jsonl
from slm_train_eval_publish.media_intent import (
    evaluate_media_action_predictions_jsonl,
    evaluate_media_actions_jsonl,
    parse_media_intent,
)


def test_parse_media_intent_outputs_function_call_shape() -> None:
    result = parse_media_intent("Show Hindi news")

    assert result.intent == "search"
    assert result.tool == "media.search"
    assert result.constraints == {"genre": "news", "live": True, "language": "hi"}
    assert result.clarification_required is False


def test_parse_media_intent_clarifies_ambiguous_query() -> None:
    result = parse_media_intent("Play Sony")

    assert result.intent == "clarify"
    assert result.tool == "media.clarify"
    assert result.missing_fields == ["specific_media"]
    assert result.clarification_required is True


def test_parse_media_intent_covers_airo_tv_rule_scenarios() -> None:
    scenarios = {
        "Marathi movie channels": ("search", "media.search", {"genre": "movies", "language": "mr"}),
        "Sports in HD only": ("search", "media.search", {"genre": "sports", "quality": "hd"}),
        "Show business news": ("search", "media.search", {"genre": "business_news", "live": True}),
        "I want devotional channels": ("recommend", "media.recommend", {"genre": "religious"}),
        "Show something educational for Class 8": (
            "recommend",
            "media.recommend",
            {"genre": "education", "grade": "8"},
        ),
        "Only free channels": ("search", "media.search", {"subscription": "free"}),
        "Kids should not see violent content": (
            "recommend",
            "media.recommend",
            {"parental_control": True, "avoid": "violence"},
        ),
        "Latest Marathi movie": (
            "search",
            "media.search",
            {"genre": "movies", "language": "mr", "sort": "recent"},
        ),
    }

    for utterance, (intent, tool, constraints) in scenarios.items():
        result = parse_media_intent(utterance)

        assert result.intent == intent, utterance
        assert result.tool == tool, utterance
        assert result.constraints == constraints, utterance


def test_evaluate_media_actions_jsonl(tmp_path: Path) -> None:
    dataset = write_media_actions_jsonl(tmp_path / "actions.jsonl", count=50, seed=4)
    report = evaluate_media_actions_jsonl(dataset)

    assert report["total"] == 50
    assert report["intent_accuracy"] >= 0.9
    assert report["tool_accuracy"] >= 0.9
    assert report["clarification_accuracy"] == 1.0

    json.dumps(report)


def test_evaluate_media_action_predictions_jsonl(tmp_path: Path) -> None:
    dataset = write_media_actions_jsonl(tmp_path / "actions.jsonl", count=40, seed=8)
    rows = [json.loads(line) for line in dataset.read_text().splitlines()]
    predictions = tmp_path / "predictions.jsonl"
    with predictions.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"input": row["input"], "output": row["output"]}))
            handle.write("\n")

    report = evaluate_media_action_predictions_jsonl(dataset, predictions)

    assert report["total"] == 40
    assert report["rule"]["intent_accuracy"] >= 0.9
    assert report["slm"]["intent_accuracy"] == 1.0
    assert report["slm"]["constraint_exact_accuracy"] == 1.0
    assert report["slm_failures"] == []
