from __future__ import annotations

from slm_train_eval_publish.adaptation_planner import (
    AdaptationPlanner,
    Constraints,
    HardwareProfile,
    PlannerContext,
)
from slm_train_eval_publish.baseline import BaselineResult
from slm_train_eval_publish.dataset_engine import DatasetProfile, TokenStats


def _dummy_profile(total: int = 1000) -> DatasetProfile:
    return DatasetProfile(
        total_examples=total,
        valid_examples=total,
        invalid_examples=0,
        duplicate_count=0,
        exact_leakage_count=0,
        normalized_leakage_count=0,
        input_tokens=TokenStats(10, 50, 25.0, 45),
        output_tokens=TokenStats(5, 20, 10.0, 18),
        class_distribution={"a": 500, "b": 500},
        schema_validity=1.0,
    )


def test_planner_recommends_baseline_when_target_met():
    baseline = BaselineResult(
        task_id="meeting.action",
        backend="rule",
        dataset_id="snap1",
        metrics={"f1": 0.92},
        latency_p50_ms=2.0,
        latency_p95_ms=5.0,
        memory_mb=16.0,
        output_validity=1.0,
        sample_count=100,
    )
    context = PlannerContext(
        task_id="meeting.action",
        task_kind="decision",
        capability_id="structured_decision",
        dataset_profile=_dummy_profile(),
        baselines=[baseline],
        constraints=Constraints(target_f1=0.85, max_latency_p95_ms=50.0),
    )

    plan = AdaptationPlanner.resolve(context)
    assert plan.method == "decision"
    assert plan.backend == "rule"
    assert "already satisfies target F1" in " ".join(plan.reasons)


def test_planner_recommends_laya_for_decision_task():
    context = PlannerContext(
        task_id="meeting.action",
        task_kind="decision",
        capability_id="structured_decision",
        dataset_profile=_dummy_profile(500),
        baselines=[],
    )
    plan = AdaptationPlanner.resolve(context)
    assert plan.method == "decision"
    assert plan.backend == "laya"


def test_planner_recommends_qlora_for_low_vram_cuda():
    hw = HardwareProfile(device="cuda", available_vram_gb=6.0)
    context = PlannerContext(
        task_id="meeting.summary",
        task_kind="generation",
        capability_id="structured_generation",
        dataset_profile=_dummy_profile(1000),
        baselines=[],
        hardware=hw,
        constraints=Constraints(target_f1=0.90),
    )
    plan = AdaptationPlanner.resolve(context)
    assert plan.method == "qlora"
    assert plan.backend == "transformers"
    assert plan.configuration["quantization"] == "4bit"
