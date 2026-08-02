from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slm_train_eval_publish.cli import app
from slm_train_eval_publish.enterprise_knowledge import (
    INTENTS,
    SYSTEM_INSTRUCTION,
    generate_enterprise_knowledge_examples,
    validate_enterprise_action,
    validate_enterprise_knowledge_jsonl,
    validate_metadata_catalog,
    write_enterprise_knowledge_split,
)


def _catalog() -> dict:
    return {
        "schema_version": "1.0",
        "knowledge_release": "enterprise-credit-2026.07.29.1",
        "entities": [
            {
                "entity_id": "concept:credit:obligation_ratio",
                "entity_type": "business_concept",
                "canonical_name": "obligation_ratio",
                "display_name": "Fixed obligation to income ratio",
                "aliases": ["FOIR", "obligation ratio"],
                "owner_team_id": "team:credit-risk",
                "verification_status": "verified",
                "source_revision": "commit-123",
            },
            {
                "entity_id": "service:underwriting-risk",
                "entity_type": "service",
                "canonical_name": "underwriting-risk-service",
                "display_name": "Underwriting risk service",
                "aliases": ["risk service"],
                "owner_team_id": "team:credit-risk",
                "verification_status": "verified",
                "source_revision": "commit-123",
            },
            {
                "entity_id": "api:underwriting-risk:foir",
                "entity_type": "api",
                "canonical_name": "post-risk-foir",
                "display_name": "POST /risk/foir",
                "aliases": ["/risk/foir"],
                "owner_team_id": "team:credit-risk",
                "verification_status": "verified",
                "source_revision": "commit-123",
            },
            {
                "entity_id": "workflow:retail-underwriting-v3",
                "entity_type": "workflow",
                "canonical_name": "retail-underwriting-v3",
                "display_name": "Retail underwriting v3",
                "aliases": ["retail underwriting"],
                "owner_team_id": "team:credit-platform",
                "verification_status": "verified",
                "source_revision": "commit-456",
            },
        ],
        "evidence": [
            {
                "evidence_id": "evidence:openapi:risk:foir",
                "citation_label": "API-RISK-FOIR-17",
                "text": (
                    "Underwriting risk service exposes POST /risk/foir for the "
                    "fixed obligation to income ratio."
                ),
                "source_uri": "repo://risk/openapi/risk.yaml",
                "source_revision": "commit-123",
                "verification_status": "verified",
            },
            {
                "evidence_id": "evidence:workflow:retail-v3",
                "citation_label": "WORKFLOW-RETAIL-V3-08",
                "text": "Retail underwriting v3 invokes POST /risk/foir.",
                "source_uri": "repo://workflow/retail-v3.yaml",
                "source_revision": "commit-456",
                "verification_status": "verified",
            },
        ],
        "relationships": [
            {
                "subject_id": "service:underwriting-risk",
                "predicate": "EXPOSES",
                "object_id": "api:underwriting-risk:foir",
                "evidence_id": "evidence:openapi:risk:foir",
                "confidence": 1.0,
                "verification_status": "verified",
            },
            {
                "subject_id": "workflow:retail-underwriting-v3",
                "predicate": "INVOKES",
                "object_id": "api:underwriting-risk:foir",
                "evidence_id": "evidence:workflow:retail-v3",
                "confidence": 0.98,
                "verification_status": "verified",
            },
        ],
        "approved_tools": [
            {
                "tool_id": "get_credit_assessment_summary",
                "description": "Get a current credit assessment summary.",
                "mode": "read_only",
                "purpose": "case_explanation",
                "required_arguments": ["case_id"],
                "example_arguments": {"case_id": "CASE-REFERENCE"},
            }
        ],
    }


def _metadata_lookup_action() -> dict:
    return {
        "schema_version": "1.0",
        "intent": "metadata_lookup",
        "entities": [{"type": "business_concept", "query": "obligation ratio"}],
        "relationship_types": ["COMPUTES", "OWNED_BY", "EVIDENCED_BY"],
        "requires_live_data": False,
        "evidence_policy": {
            "minimum_status": "verified",
            "citations_required": True,
        },
        "tool_call": None,
        "answer": None,
        "citations": [],
        "abstain": False,
        "reason": None,
    }


def test_validate_metadata_catalog_accepts_governed_references() -> None:
    validate_metadata_catalog(_catalog())


def test_validate_metadata_catalog_rejects_unknown_relationship_reference() -> None:
    catalog = _catalog()
    catalog["relationships"][0]["object_id"] = "api:missing"

    with pytest.raises(ValueError, match="unknown object_id"):
        validate_metadata_catalog(catalog)


def test_validate_metadata_catalog_rejects_write_tools() -> None:
    catalog = _catalog()
    catalog["approved_tools"][0]["mode"] = "read_write"

    with pytest.raises(ValueError, match="read_only"):
        validate_metadata_catalog(catalog)


def test_validate_enterprise_action_accepts_metadata_lookup() -> None:
    validate_enterprise_action(_metadata_lookup_action())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda action: action.update(schema_version="2.0"), "schema_version"),
        (lambda action: action.update(intent="execute_sql"), "intent"),
        (lambda action: action.update(relationship_types=["UNKNOWN"]), "relationship"),
        (lambda action: action.update(unexpected=True), "fields"),
    ],
)
def test_validate_enterprise_action_rejects_invalid_contract(mutation, message: str) -> None:
    action = _metadata_lookup_action()
    mutation(action)

    with pytest.raises(ValueError, match=message):
        validate_enterprise_action(action)


def test_validate_enterprise_action_requires_citations_for_grounded_answer() -> None:
    action = _metadata_lookup_action()
    action.update(
        intent="grounded_answer",
        answer="The service exposes the ratio API.",
        citations=[],
    )

    with pytest.raises(ValueError, match="citation"):
        validate_enterprise_action(action)


def test_validate_enterprise_action_rejects_non_read_only_tool_call() -> None:
    action = _metadata_lookup_action()
    action.update(
        intent="live_data_lookup",
        requires_live_data=True,
        tool_call={
            "tool": "update_credit_case",
            "arguments": {"case_id": "CASE-REFERENCE"},
            "purpose": "case_explanation",
            "mode": "write",
        },
    )

    with pytest.raises(ValueError, match="read_only"):
        validate_enterprise_action(action)


def test_generate_examples_cover_training_families_and_validate() -> None:
    examples = generate_enterprise_knowledge_examples(_catalog(), count=200, seed=7)

    assert len(examples) == 200
    assert {example.family for example in examples} == {
        "metadata_lookup",
        "grounded_answer",
        "live_data_lookup",
        "abstain",
    }

    for example in examples:
        row = example.to_sft_row()
        assert set(row) == {"instruction", "input", "output"}
        assert row["instruction"] == SYSTEM_INSTRUCTION
        validate_enterprise_action(
            json.loads(row["output"]),
            approved_tool_ids={"get_credit_assessment_summary"},
        )


def test_generate_examples_add_policy_safe_request_diversity() -> None:
    examples = generate_enterprise_knowledge_examples(_catalog(), count=400, seed=31)

    assert len({example.user_input for example in examples}) >= 300
    assert all("Constraint:" in example.user_input for example in examples)


def test_write_split_is_deterministic_and_valid(tmp_path: Path) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    train_path, eval_path = write_enterprise_knowledge_split(
        catalog_path=catalog_path,
        train_output=tmp_path / "train.jsonl",
        eval_output=tmp_path / "eval.jsonl",
        train_count=32,
        eval_count=12,
        seed=11,
    )
    repeated_train, repeated_eval = write_enterprise_knowledge_split(
        catalog_path=catalog_path,
        train_output=tmp_path / "repeated-train.jsonl",
        eval_output=tmp_path / "repeated-eval.jsonl",
        train_count=32,
        eval_count=12,
        seed=11,
    )

    assert train_path.read_text() == repeated_train.read_text()
    assert eval_path.read_text() == repeated_eval.read_text()
    assert train_path.read_text().splitlines()[0] != eval_path.read_text().splitlines()[0]
    assert validate_enterprise_knowledge_jsonl(train_path, catalog_path=catalog_path) == 32
    assert validate_enterprise_knowledge_jsonl(eval_path, catalog_path=catalog_path) == 12


def test_write_split_balances_schema_corrections_across_intents(tmp_path: Path) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    train_path, _ = write_enterprise_knowledge_split(
        catalog_path=catalog_path,
        train_output=tmp_path / "train.jsonl",
        eval_output=tmp_path / "eval.jsonl",
        train_count=32,
        eval_count=4,
        seed=21,
    )

    correction_counts = {
        "metadata_lookup": 0,
        "grounded_answer": 0,
        "live_data_lookup": 0,
        "abstain": 0,
    }
    for line in train_path.read_text().splitlines():
        row = json.loads(line)
        action = json.loads(row["output"])
        if row["input"].startswith("Untrusted invalid prior draft:"):
            correction_counts[action["intent"]] += 1

    assert correction_counts == {
        "metadata_lookup": 2,
        "grounded_answer": 2,
        "live_data_lookup": 2,
        "abstain": 2,
    }


def test_write_split_supports_catalog_grounded_blueprint_instruction(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    train_path, _ = write_enterprise_knowledge_split(
        catalog_path=catalog_path,
        train_output=tmp_path / "train.jsonl",
        eval_output=tmp_path / "eval.jsonl",
        train_count=4,
        eval_count=4,
        instruction_mode="blueprint",
    )

    rows = [json.loads(line) for line in train_path.read_text().splitlines()]
    instructions = {row["instruction"] for row in rows}
    assert len(instructions) == 1
    instruction = instructions.pop()
    assert "Enterprise Knowledge Action v1" in instruction
    assert "get_credit_assessment_summary" in instruction
    assert "EXPOSES" in instruction


def test_write_split_rejects_unknown_instruction_mode(tmp_path: Path) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    with pytest.raises(ValueError, match="instruction_mode"):
        write_enterprise_knowledge_split(
            catalog_path=catalog_path,
            train_output=tmp_path / "train.jsonl",
            eval_output=tmp_path / "eval.jsonl",
            train_count=4,
            eval_count=4,
            instruction_mode="invented",
        )


def test_safety_v2_doubles_balanced_correction_examples(tmp_path: Path) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    train_path, _ = write_enterprise_knowledge_split(
        catalog_path=catalog_path,
        train_output=tmp_path / "train.jsonl",
        eval_output=tmp_path / "eval.jsonl",
        train_count=32,
        eval_count=8,
        seed=21,
        augmentation_profile="safety_v2",
    )

    correction_counts = {intent: 0 for intent in INTENTS}
    for line in train_path.read_text().splitlines():
        row = json.loads(line)
        action = json.loads(row["output"])
        if row["input"].startswith("Untrusted invalid prior draft:"):
            correction_counts[action["intent"]] += 1

    assert correction_counts == {intent: 4 for intent in INTENTS}


def test_write_split_rejects_unknown_augmentation_profile(tmp_path: Path) -> None:
    catalog_path = tmp_path / "metadata.json"
    catalog_path.write_text(json.dumps(_catalog()), encoding="utf-8")

    with pytest.raises(ValueError, match="augmentation_profile"):
        write_enterprise_knowledge_split(
            catalog_path=catalog_path,
            train_output=tmp_path / "train.jsonl",
            eval_output=tmp_path / "eval.jsonl",
            train_count=4,
            eval_count=4,
            augmentation_profile="unsafe",
        )


def test_enterprise_split_cli_exposes_instruction_mode() -> None:
    result = CliRunner().invoke(
        app,
        ["generate-enterprise-knowledge-splits", "--help"],
    )

    assert result.exit_code == 0
    assert "--instruction-mode" in result.stdout
    assert "--augmentation-profile" in result.stdout
