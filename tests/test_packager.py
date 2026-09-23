from __future__ import annotations

from pathlib import Path

from slm_train_eval_publish.adaptation_planner import AdaptationPlan
from slm_train_eval_publish.execution import ExecutionEngine
from slm_train_eval_publish.packager import package_intelligence_pack


def test_package_intelligence_pack(tmp_path: Path):
    plan = AdaptationPlan(method="decision", backend="laya")
    engine = ExecutionEngine()
    res = engine.execute(plan=plan, project_dir=tmp_path)

    pack = package_intelligence_pack(project_dir=tmp_path, experiment_id=res.experiment_id)

    assert pack.experiment_id == res.experiment_id
    assert Path(pack.output_path).exists()
    assert pack.output_path.endswith(".pack")
