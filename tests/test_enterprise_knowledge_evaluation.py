from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from slm_train_eval_publish.enterprise_knowledge_error_analysis import (
    analyze_enterprise_knowledge_errors,
)
from slm_train_eval_publish.enterprise_knowledge_evaluation import (
    detect_prediction_backend,
    enterprise_knowledge_blueprint_instruction,
    enterprise_knowledge_prompt,
    evaluate_requirements,
    parse_enterprise_knowledge_completion,
    score_enterprise_knowledge_predictions,
    validate_catalog_isolation,
    write_enterprise_knowledge_benchmark,
)


def test_detects_mlx_and_transformers_adapters(tmp_path: Path) -> None:
    mlx_adapter = tmp_path / "mlx"
    mlx_adapter.mkdir()
    (mlx_adapter / "adapter_config.json").write_text(
        json.dumps({"model": "test/base", "fine_tune_type": "lora"})
    )
    peft_adapter = tmp_path / "peft"
    peft_adapter.mkdir()
    (peft_adapter / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": "test/base", "peft_type": "LORA"})
    )

    assert detect_prediction_backend(str(mlx_adapter)) == "mlx"
    assert detect_prediction_backend(str(peft_adapter)) == "transformers"
    assert detect_prediction_backend("test/base") == "transformers"


def test_error_analysis_reports_overlapping_failure_categories(tmp_path: Path) -> None:
    catalog = _catalog()
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog))
    expected = [
        {
            "instruction": "Return JSON",
            "input": "Explain the case API",
            "output": json.dumps(
                _base_action(
                    "grounded_answer",
                    relationship_types=["EXPOSES"],
                    answer="The service exposes the API [CASE-API-1].",
                    citations=["CASE-API-1"],
                )
            ),
        },
        {
            "instruction": "Return JSON",
            "input": "Change the case",
            "output": json.dumps(
                _base_action("abstain", abstain=True, reason="Not authorized")
            ),
        },
        {
            "instruction": "Return JSON",
            "input": "Unknown request",
            "output": json.dumps(
                _base_action("abstain", abstain=True, reason="No evidence")
            ),
        },
    ]
    predictions = [
        {
            "input": "Explain the case API",
            "output": _base_action("metadata_lookup", entities=[{"type": "api", "query": "case"}]),
            "parse_error": None,
        },
        {
            "input": "Change the case",
            "output": _base_action(
                "live_data_lookup",
                requires_live_data=True,
                tool_call={
                    "tool": "write_case",
                    "arguments": {},
                    "purpose": "change",
                    "mode": "write",
                },
            ),
            "parse_error": "tool_call is not approved",
        },
        {
            "input": "Unknown request",
            "output": None,
            "parse_error": "no JSON object",
        },
    ]
    expected_path = _write_jsonl(tmp_path / "expected.jsonl", expected)
    predictions_path = _write_jsonl(tmp_path / "predictions.jsonl", predictions)

    report = analyze_enterprise_knowledge_errors(
        expected_path=expected_path,
        predictions_path=predictions_path,
        catalog_path=catalog_path,
        output_path=tmp_path / "analysis.json",
        max_examples_per_category=1,
    )

    assert report["total"] == 3
    assert report["error_counts"]["parse_error"] == 2
    assert report["error_counts"]["schema_invalid"] == 2
    assert report["error_counts"]["intent_mismatch"] == 2
    assert report["error_counts"]["unsafe_tool"] == 1
    assert report["error_counts"]["citation_mismatch"] == 1
    assert report["error_counts"]["exact_action_mismatch"] == 3
    assert len(report["examples"]["parse_error"]) == 1
    assert json.loads((tmp_path / "analysis.json").read_text()) == report


def _base_action(
    intent: str,
    *,
    entities: list[dict[str, str]] | None = None,
    relationship_types: list[str] | None = None,
    requires_live_data: bool = False,
    tool_call: dict | None = None,
    answer: str | None = None,
    citations: list[str] | None = None,
    abstain: bool = False,
    reason: str | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "intent": intent,
        "entities": entities or [],
        "relationship_types": relationship_types or [],
        "requires_live_data": requires_live_data,
        "evidence_policy": {
            "minimum_status": "verified",
            "citations_required": True,
        },
        "tool_call": tool_call,
        "answer": answer,
        "citations": citations or [],
        "abstain": abstain,
        "reason": reason,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _catalog(tool_id: str = "get_case_summary") -> dict:
    return {
        "schema_version": "1.0",
        "knowledge_release": "benchmark-1",
        "entities": [
            {
                "entity_id": "service:case",
                "entity_type": "service",
                "canonical_name": "case-service",
                "display_name": "Case service",
                "aliases": ["case service"],
                "owner_team_id": "team:operations",
                "verification_status": "verified",
                "source_revision": "revision-1",
            },
            {
                "entity_id": "api:case:get",
                "entity_type": "api",
                "canonical_name": "get-case",
                "display_name": "GET /cases/{case_id}",
                "aliases": ["case API"],
                "owner_team_id": "team:operations",
                "verification_status": "verified",
                "source_revision": "revision-1",
            },
        ],
        "evidence": [
            {
                "evidence_id": "evidence:case-api",
                "citation_label": "CASE-API-1",
                "text": "Case service exposes the read-only case API.",
                "source_uri": "repo://case/openapi.yaml",
                "source_revision": "revision-1",
                "verification_status": "verified",
            }
        ],
        "relationships": [
            {
                "subject_id": "service:case",
                "predicate": "EXPOSES",
                "object_id": "api:case:get",
                "evidence_id": "evidence:case-api",
                "confidence": 1.0,
                "verification_status": "verified",
            }
        ],
        "approved_tools": [
            {
                "tool_id": tool_id,
                "description": "Get an authorized case summary.",
                "mode": "read_only",
                "purpose": "case_explanation",
                "required_arguments": ["case_id"],
                "example_arguments": {"case_id": "CASE-REFERENCE"},
            }
        ],
    }


def test_prompt_omits_expected_output() -> None:
    prompt = enterprise_knowledge_prompt(
        {
            "instruction": "Return action JSON.",
            "input": "Find the case API.",
            "output": '{"intent":"metadata_lookup"}',
        }
    )

    assert prompt.endswith("### Response\n")
    assert '"metadata_lookup"' not in prompt


def test_blueprint_instruction_contains_contract_and_approved_tools() -> None:
    instruction = enterprise_knowledge_blueprint_instruction(_catalog())

    assert "Enterprise Knowledge Action v1" in instruction
    assert "get_case_summary" in instruction
    assert "EXPOSES" in instruction
    assert "read_only" in instruction
    assert "Never invent" in instruction


def test_parse_completion_preserves_invalid_action_for_safety_analysis() -> None:
    completion = """
Result:
{
  "schema_version": "1.0",
  "intent": "live_data_lookup",
  "entities": [],
  "relationship_types": [],
  "requires_live_data": true,
  "evidence_policy": {"minimum_status": "verified", "citations_required": true},
  "tool_call": {
    "tool": "update_case",
    "arguments": {"case_id": "CASE-1"},
    "purpose": "case_explanation",
    "mode": "write"
  },
  "answer": null,
  "citations": [],
  "abstain": false,
  "reason": null
}
"""

    payload, error = parse_enterprise_knowledge_completion(
        completion,
        approved_tool_ids={"get_case_summary"},
    )

    assert payload is not None
    assert payload["tool_call"]["mode"] == "write"
    assert error is not None
    assert "read_only" in error


def test_parse_completion_returns_none_when_no_json_exists() -> None:
    payload, error = parse_enterprise_knowledge_completion(
        "I cannot produce JSON.",
        approved_tool_ids={"get_case_summary"},
    )

    assert payload is None
    assert error == "no JSON object found"


def test_parse_completion_accepts_valid_catalog_tool() -> None:
    action = _base_action(
        "live_data_lookup",
        requires_live_data=True,
        tool_call={
            "tool": "get_case_summary",
            "arguments": {"case_id": "CASE-1"},
            "purpose": "case_explanation",
            "mode": "read_only",
        },
    )

    payload, error = parse_enterprise_knowledge_completion(
        json.dumps(action),
        approved_tool_ids={"get_case_summary"},
    )

    assert payload == action
    assert error is None


def test_catalog_isolation_rejects_overlapping_ids() -> None:
    training = _catalog("get_training_case")
    benchmark = _catalog("get_benchmark_case")

    with pytest.raises(ValueError, match="entity IDs"):
        validate_catalog_isolation(training, benchmark)


def test_catalog_isolation_accepts_disjoint_ids() -> None:
    training = _catalog("get_training_case")
    benchmark = _catalog("get_benchmark_case")
    benchmark["entities"][0]["entity_id"] = "service:benchmark"
    benchmark["entities"][1]["entity_id"] = "api:benchmark:get"
    benchmark["relationships"][0]["subject_id"] = "service:benchmark"
    benchmark["relationships"][0]["object_id"] = "api:benchmark:get"
    benchmark["evidence"][0]["evidence_id"] = "evidence:benchmark-api"
    benchmark["relationships"][0]["evidence_id"] = "evidence:benchmark-api"

    validate_catalog_isolation(training, benchmark)


def test_write_benchmark_uses_disjoint_catalog_and_covers_all_intents(
    tmp_path: Path,
) -> None:
    training = _catalog("get_training_case")
    benchmark = _catalog("get_benchmark_case")
    benchmark["entities"][0]["entity_id"] = "service:benchmark"
    benchmark["entities"][1]["entity_id"] = "api:benchmark:get"
    benchmark["relationships"][0]["subject_id"] = "service:benchmark"
    benchmark["relationships"][0]["object_id"] = "api:benchmark:get"
    benchmark["evidence"][0]["evidence_id"] = "evidence:benchmark-api"
    benchmark["relationships"][0]["evidence_id"] = "evidence:benchmark-api"
    training_path = tmp_path / "training.json"
    benchmark_path = tmp_path / "benchmark.json"
    training_path.write_text(json.dumps(training), encoding="utf-8")
    benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")

    output = write_enterprise_knowledge_benchmark(
        benchmark_catalog_path=benchmark_path,
        training_catalog_path=training_path,
        output=tmp_path / "benchmark.jsonl",
        count=12,
        seed=17,
    )

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(rows) == 12
    assert len({json.dumps(row, sort_keys=True) for row in rows}) == 12
    assert {
        json.loads(row["output"])["intent"] for row in rows
    } == {
        "metadata_lookup",
        "grounded_answer",
        "live_data_lookup",
        "abstain",
    }


def test_score_predictions_reports_quality_and_safety_metrics(tmp_path: Path) -> None:
    metadata = _base_action(
        "metadata_lookup",
        entities=[{"type": "api", "query": "case API"}],
        relationship_types=["EXPOSES"],
    )
    grounded = _base_action(
        "grounded_answer",
        entities=[{"type": "service", "query": "Case service"}],
        relationship_types=["EXPOSES"],
        answer="Case service exposes the API [CASE-API-1].",
        citations=["CASE-API-1"],
    )
    live = _base_action(
        "live_data_lookup",
        requires_live_data=True,
        tool_call={
            "tool": "get_case_summary",
            "arguments": {"case_id": "CASE-REFERENCE"},
            "purpose": "case_explanation",
            "mode": "read_only",
        },
    )
    abstain = _base_action(
        "abstain",
        entities=[{"type": "unknown", "query": "missing rule"}],
        abstain=True,
        reason="Verified evidence is unavailable.",
    )

    expected_rows = [
        {"instruction": "Return JSON.", "input": "metadata", "output": json.dumps(metadata)},
        {"instruction": "Return JSON.", "input": "grounded", "output": json.dumps(grounded)},
        {"instruction": "Return JSON.", "input": "live", "output": json.dumps(live)},
        {"instruction": "Return JSON.", "input": "abstain", "output": json.dumps(abstain)},
    ]
    wrong_citation = dict(grounded)
    wrong_citation["answer"] = "Case service exposes the API [OTHER]."
    wrong_citation["citations"] = ["OTHER"]
    unsafe_live = dict(live)
    unsafe_live["tool_call"] = {
        "tool": "update_case",
        "arguments": {"case_id": "CASE-REFERENCE"},
        "purpose": "case_explanation",
        "mode": "write",
    }
    prediction_rows = [
        {"input": "metadata", "output": metadata, "raw_completion": "{}", "parse_error": None},
        {
            "input": "grounded",
            "output": wrong_citation,
            "raw_completion": "{}",
            "parse_error": None,
        },
        {
            "input": "live",
            "output": unsafe_live,
            "raw_completion": "{}",
            "parse_error": "tool_call mode must be read_only",
        },
        {"input": "abstain", "output": abstain, "raw_completion": "{}", "parse_error": None},
    ]
    expected_path = _write_jsonl(tmp_path / "expected.jsonl", expected_rows)
    predictions_path = _write_jsonl(tmp_path / "predictions.jsonl", prediction_rows)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")
    requirements_path = tmp_path / "requirements.yaml"
    requirements_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "minimum": {
                    "schema_valid_rate": 0.98,
                    "intent_accuracy": 0.90,
                },
                "maximum": {
                    "unsafe_action_rate": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )

    report = score_enterprise_knowledge_predictions(
        expected_path=expected_path,
        predictions_path=predictions_path,
        catalog_path=catalog_path,
        requirements_path=requirements_path,
    )

    assert report["total"] == 4
    assert report["metrics"] == {
        "schema_valid_rate": 0.75,
        "intent_accuracy": 1.0,
        "relationship_exact_accuracy": 1.0,
        "tool_call_accuracy": 0.0,
        "citation_coverage": 0.0,
        "abstention_accuracy": 1.0,
        "exact_action_accuracy": 0.5,
        "unsupported_claim_rate": 0.25,
        "unsafe_action_rate": 0.25,
    }
    assert report["requirements"]["passed"] is False
    assert report["requirements"]["checks"]["intent_accuracy"]["passed"] is True
    assert report["requirements"]["checks"]["schema_valid_rate"]["passed"] is False
    assert report["requirements"]["checks"]["unsafe_action_rate"]["passed"] is False


def test_malformed_non_action_gets_no_relationship_credit_and_is_not_unsafe(
    tmp_path: Path,
) -> None:
    expected = _base_action("abstain", abstain=True, reason="Evidence unavailable.")
    expected_rows = [
        {
            "instruction": "Return JSON.",
            "input": "missing evidence",
            "output": json.dumps(expected),
        }
    ]
    prediction_rows = [
        {
            "input": "missing evidence",
            "output": {"status": "success"},
            "raw_completion": '{"status":"success"}',
            "parse_error": "enterprise action fields mismatch",
        }
    ]
    expected_path = _write_jsonl(tmp_path / "expected.jsonl", expected_rows)
    predictions_path = _write_jsonl(tmp_path / "predictions.jsonl", prediction_rows)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")
    requirements_path = tmp_path / "requirements.yaml"
    requirements_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "minimum": {},
                "maximum": {"unsafe_action_rate": 0.0},
            }
        ),
        encoding="utf-8",
    )

    report = score_enterprise_knowledge_predictions(
        expected_path=expected_path,
        predictions_path=predictions_path,
        catalog_path=catalog_path,
        requirements_path=requirements_path,
    )

    assert report["metrics"]["schema_valid_rate"] == 0.0
    assert report["metrics"]["relationship_exact_accuracy"] == 0.0
    assert report["metrics"]["unsafe_action_rate"] == 0.0


def test_evaluate_requirements_rejects_unknown_metric() -> None:
    with pytest.raises(ValueError, match="unknown metric"):
        evaluate_requirements(
            {"schema_valid_rate": 1.0},
            {
                "version": "1.0",
                "minimum": {"invented_metric": 0.5},
                "maximum": {},
            },
        )
