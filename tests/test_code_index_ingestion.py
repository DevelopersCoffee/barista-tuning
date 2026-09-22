from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slm_train_eval_publish.cli import app
from slm_train_eval_publish.code_index_ingestion import compile_code_index_export
from slm_train_eval_publish.enterprise_knowledge import validate_metadata_catalog


def _export() -> dict:
    return {
        "schema_version": "1.0",
        "knowledge_release": "code-index-2026.08.02.1",
        "source_revision": "commit-abc123",
        "extractor": {"id": "generic-index-adapter", "version": "1.0.0"},
        "symbols": [
            {
                "symbol_id": "service:risk",
                "kind": "service",
                "name": "Risk service",
                "qualified_name": "internal.risk.RiskService",
                "language": "java",
                "path": "services/risk/src/RiskService.java",
                "line_start": 12,
                "line_end": 88,
                "owner_team_id": "team:risk",
                "verification_status": "verified",
            },
            {
                "symbol_id": "api:risk:ratio",
                "kind": "api_operation",
                "name": "POST /risk/ratio",
                "qualified_name": "internal.risk.RiskController.calculateRatio",
                "language": "java",
                "path": "services/risk/src/RiskController.java",
                "line_start": 41,
                "line_end": 63,
                "owner_team_id": "team:risk",
                "verification_status": "verified",
            },
        ],
        "relationships": [
            {
                "subject_id": "service:risk",
                "predicate": "EXPOSES",
                "object_id": "api:risk:ratio",
                "source_path": "services/risk/src/RiskController.java",
                "line_start": 41,
                "line_end": 63,
                "confidence": 1.0,
                "verification_status": "verified",
            }
        ],
    }


def _write_export(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_compiles_code_index_export_into_governed_catalog(tmp_path: Path) -> None:
    output = compile_code_index_export(_write_export(tmp_path, _export()), tmp_path / "out")

    catalog = json.loads(output.read_text())
    validate_metadata_catalog(catalog)
    assert output == tmp_path / "out" / "metadata_catalog.json"
    assert [entity["entity_id"] for entity in catalog["entities"]] == [
        "api:risk:ratio",
        "service:risk",
    ]
    assert all(entity["evidence_ids"] for entity in catalog["entities"])
    assert catalog["relationships"][0]["predicate"] == "EXPOSES"
    assert catalog["approved_tools"] == []


def test_code_index_compilation_is_byte_deterministic(tmp_path: Path) -> None:
    source = _write_export(tmp_path, _export())

    first = compile_code_index_export(source, tmp_path / "first")
    second = compile_code_index_export(source, tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()


def test_rejects_broken_relationship_before_writing(tmp_path: Path) -> None:
    payload = _export()
    payload["relationships"][0]["object_id"] = "api:missing"
    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="unknown object_id"):
        compile_code_index_export(_write_export(tmp_path, payload), output_dir)

    assert not output_dir.exists()


@pytest.mark.parametrize("path", ["../secret.env", "/etc/passwd", "src\\secret.java"])
def test_rejects_unsafe_source_paths(tmp_path: Path, path: str) -> None:
    payload = _export()
    payload["symbols"][0]["path"] = path

    with pytest.raises(ValueError, match="repository-relative"):
        compile_code_index_export(_write_export(tmp_path, payload), tmp_path / "out")


def test_rejects_raw_source_body(tmp_path: Path) -> None:
    payload = _export()
    payload["symbols"][0]["source_code"] = "credential = 'do-not-index'"

    with pytest.raises(ValueError, match="fields mismatch"):
        compile_code_index_export(_write_export(tmp_path, payload), tmp_path / "out")


def test_compile_code_index_cli(tmp_path: Path) -> None:
    source = _write_export(tmp_path, _export())

    result = CliRunner().invoke(
        app,
        ["compile-code-index", str(source), "--output", str(tmp_path / "compiled")],
    )

    assert result.exit_code == 0
    assert (tmp_path / "compiled" / "metadata_catalog.json").exists()
