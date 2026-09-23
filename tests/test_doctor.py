from __future__ import annotations

import json
from pathlib import Path

from slm_train_eval_publish.doctor import run_doctor, run_plan


def test_run_doctor_and_plan_on_empty_dir(tmp_path: Path):
    report = run_doctor(tmp_path)
    assert report["project_dir"] == str(tmp_path)
    assert len(report["health_checks"]) == 2
    assert report["adaptation_plan"]["method"] is not None


def test_run_doctor_with_valid_dataset(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    train_file = data_dir / "train.jsonl"
    data = [{"input": f"Test {i}", "output": f"Out {i}"} for i in range(10)]
    train_file.write_text("\n".join(json.dumps(d) for d in data) + "\n")

    report = run_doctor(tmp_path)
    dataset_profile = report["dataset_profile"]
    assert dataset_profile is not None
    assert dataset_profile["total_examples"] == 10

    plan = run_plan(tmp_path)
    assert plan.method in ("decision", "prompt", "lora", "qlora", "rag")
    assert len(plan.reasons) > 0
