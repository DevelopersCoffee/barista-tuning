from __future__ import annotations

from pathlib import Path

import pytest
from slm_train_eval_publish.adaptation_planner import AdaptationPlan
from slm_train_eval_publish.evaluation_engine import EvaluationEngine
from slm_train_eval_publish.execution import ExecutionEngine


def test_evaluation_engine_evaluates_experiment(tmp_path: Path):
    plan = AdaptationPlan(method="decision", backend="laya")
    engine = ExecutionEngine()
    res = engine.execute(plan=plan, project_dir=tmp_path)

    eval_engine = EvaluationEngine()
    report = eval_engine.evaluate_experiment(
        experiment_id=res.experiment_id,
        project_dir=tmp_path,
        target_f1=0.85,
        max_latency_p95_ms=50.0,
    )

    assert report.overall_pass is True
    assert len(report.gates) == 4
    assert all(g.passed for g in report.gates)
