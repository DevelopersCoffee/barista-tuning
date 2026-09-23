from __future__ import annotations

from pathlib import Path

from slm_train_eval_publish.adaptation_planner import AdaptationPlan
from slm_train_eval_publish.execution import ExecutionEngine
from slm_train_eval_publish.experiment import ExperimentTracker, compare_experiments


def test_execution_engine_executes_decision_plan(tmp_path: Path):
    plan = AdaptationPlan(
        method="decision",
        backend="laya",
        configuration={"threshold": 0.85},
        reasons=["decision task"],
    )
    engine = ExecutionEngine()
    res = engine.execute(plan=plan, project_dir=tmp_path, snapshot_id="snap123")

    assert res.experiment_id.startswith("exp-")
    assert res.metrics["accuracy"] == 0.92
    assert Path(res.output_path).exists()
    assert (Path(res.output_path) / "decision_model.json").exists()

    tracker = ExperimentTracker()
    records = tracker.list_experiments(tmp_path)
    assert len(records) == 1
    assert records[0].id == res.experiment_id

    cmp_output = compare_experiments(records)
    assert "Compared 1 experiments." in cmp_output


def test_execution_engine_executes_qlora_plan(tmp_path: Path):
    plan = AdaptationPlan(
        method="qlora",
        backend="transformers",
        configuration={"quantization": "4bit", "rank": 16},
        reasons=["vram limit"],
    )
    engine = ExecutionEngine()
    res = engine.execute(plan=plan, project_dir=tmp_path, snapshot_id="snap456")

    assert res.metrics["memory_mb"] == 1200.0
    assert (Path(res.output_path) / "adapter" / "adapter_config.json").exists()
