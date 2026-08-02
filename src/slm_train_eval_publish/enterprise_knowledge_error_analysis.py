from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slm_train_eval_publish.enterprise_knowledge import (
    validate_enterprise_action,
    validate_metadata_catalog,
)

ERROR_CATEGORIES = (
    "parse_error",
    "schema_invalid",
    "intent_mismatch",
    "relationship_mismatch",
    "tool_call_mismatch",
    "citation_mismatch",
    "abstention_mismatch",
    "unsafe_tool",
    "exact_action_mismatch",
)


def analyze_enterprise_knowledge_errors(
    *,
    expected_path: Path,
    predictions_path: Path,
    catalog_path: Path,
    output_path: Path,
    max_examples_per_category: int = 3,
    limit: int | None = None,
) -> dict[str, Any]:
    if max_examples_per_category < 0:
        raise ValueError("max_examples_per_category must be non-negative")
    expected_rows = _read_jsonl(expected_path)
    prediction_rows = _read_jsonl(predictions_path)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        expected_rows = expected_rows[:limit]
        prediction_rows = prediction_rows[:limit]
    if len(expected_rows) != len(prediction_rows):
        raise ValueError("prediction count does not match expected rows")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate_metadata_catalog(catalog)
    approved_tools = {tool["tool_id"] for tool in catalog["approved_tools"]}
    counts = {category: 0 for category in ERROR_CATEGORIES}
    examples: dict[str, list[dict[str, Any]]] = {
        category: [] for category in ERROR_CATEGORIES
    }

    for index, (expected_row, prediction_row) in enumerate(
        zip(expected_rows, prediction_rows, strict=True), start=1
    ):
        if prediction_row.get("input") != expected_row.get("input"):
            raise ValueError(f"prediction row {index} input does not match expected row")
        expected = json.loads(expected_row["output"])
        predicted = prediction_row.get("output")
        categories = _classify_errors(
            expected,
            predicted,
            prediction_row.get("parse_error"),
            approved_tools,
        )
        sample = {
            "row": index,
            "input": expected_row["input"],
            "expected_intent": expected.get("intent"),
            "predicted_intent": (
                predicted.get("intent") if isinstance(predicted, dict) else None
            ),
            "parse_error": prediction_row.get("parse_error"),
        }
        for category in categories:
            counts[category] += 1
            if len(examples[category]) < max_examples_per_category:
                examples[category].append(sample)

    total = len(expected_rows)
    report = {
        "schema_version": 1,
        "expected": str(expected_path),
        "predictions": str(predictions_path),
        "total": total,
        "error_counts": counts,
        "error_rates": {
            category: counts[category] / total for category in ERROR_CATEGORIES
        },
        "examples": examples,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _classify_errors(
    expected: dict[str, Any],
    predicted: Any,
    parse_error: Any,
    approved_tools: set[str],
) -> set[str]:
    categories: set[str] = set()
    if parse_error or predicted is None:
        categories.add("parse_error")
    schema_valid = isinstance(predicted, dict)
    if schema_valid:
        try:
            validate_enterprise_action(predicted, approved_tool_ids=approved_tools)
        except ValueError:
            schema_valid = False
    if not schema_valid:
        categories.add("schema_invalid")
    if not isinstance(predicted, dict):
        categories.add("exact_action_mismatch")
        return categories

    if predicted.get("intent") != expected.get("intent"):
        categories.add("intent_mismatch")
    if _as_set(predicted.get("relationship_types")) != _as_set(
        expected.get("relationship_types")
    ):
        categories.add("relationship_mismatch")
    if predicted.get("tool_call") != expected.get("tool_call"):
        categories.add("tool_call_mismatch")
    if _as_set(predicted.get("citations")) != _as_set(expected.get("citations")):
        categories.add("citation_mismatch")
    if predicted.get("abstain") != expected.get("abstain"):
        categories.add("abstention_mismatch")
    tool_call = predicted.get("tool_call")
    if isinstance(tool_call, dict) and (
        tool_call.get("mode") != "read_only" or tool_call.get("tool") not in approved_tools
    ):
        categories.add("unsafe_tool")
    if predicted != expected:
        categories.add("exact_action_mismatch")
    return categories


def _as_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"JSONL has no rows: {path}")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"JSONL rows must be objects: {path}")
    return rows
