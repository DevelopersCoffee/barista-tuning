from __future__ import annotations

import json
from pathlib import Path

import pytest
from slm_train_eval_publish.capability import Capability, get_capability_registry
from slm_train_eval_publish.dataset_engine import (
    DatasetPreparationConfig,
    compute_dataset_id,
    inspect_dataset,
    prepare_dataset,
)


def test_capability_registry_defaults():
    registry = get_capability_registry()
    decision_cap = registry.get("structured_decision")
    assert decision_cap is not None
    assert decision_cap.name == "Structured Decision"
    assert "deterministic" in decision_cap.supported_backends
    assert "laya" in decision_cap.supported_backends
    assert "jev" in decision_cap.supported_backends


def test_inspect_dataset_read_only(tmp_path: Path):
    source_file = tmp_path / "train.jsonl"
    data = [
        {"input": "Turn on TV", "label": "media_play"},
        {"input": "Play news", "label": "media_play"},
        {"input": "Turn on TV", "label": "media_play"},  # Duplicate
    ]
    source_file.write_text("\n".join(json.dumps(d) for d in data) + "\n")

    profile = inspect_dataset(source_file)
    assert profile.total_examples == 3
    assert profile.valid_examples == 3
    assert profile.duplicate_count == 1
    assert profile.schema_validity == 1.0
    assert len(profile.quality_warnings) > 0


def test_prepare_dataset_creates_immutable_snapshot(tmp_path: Path):
    source_file = tmp_path / "raw_train.jsonl"
    data = [
        {"input": f"Example {i}", "output": f"Output {i}", "label": "action"}
        for i in range(20)
    ]
    source_file.write_text("\n".join(json.dumps(d) for d in data) + "\n")

    config = DatasetPreparationConfig(train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42)
    res = prepare_dataset(source_path=source_file, output_dir=tmp_path, config=config)

    dataset_id = res["dataset_id"]
    snapshot_dir = Path(res["snapshot_dir"])
    assert snapshot_dir.exists()
    assert (snapshot_dir / "manifest.json").exists()
    assert (snapshot_dir / "profile.json").exists()
    assert (snapshot_dir / "train.jsonl").exists()
    assert (snapshot_dir / "validation.jsonl").exists()
    assert (snapshot_dir / "test.jsonl").exists()

    manifest = res["manifest"]
    assert manifest["splits"]["train"]["count"] == 16
    assert manifest["splits"]["validation"]["count"] == 2
    assert manifest["splits"]["test"]["count"] == 2


def test_dataset_id_includes_prep_config(tmp_path: Path):
    cfg1 = DatasetPreparationConfig(seed=42)
    cfg2 = DatasetPreparationConfig(seed=100)

    id1 = compute_dataset_id("data", "schema", cfg1)
    id2 = compute_dataset_id("data", "schema", cfg2)

    assert id1 != id2
