from __future__ import annotations

from slm_train_eval_publish.baseline import (
    BaselineEngine,
    DecisionBaselineEvaluator,
    PromptBaselineEvaluator,
    RuleBaselineEvaluator,
)


def test_baseline_engine_runs_all_backends():
    engine = BaselineEngine()
    examples = [
        {"input": "turn on tv", "output": "media_play"},
        {"input": "pause video", "output": "media_pause"},
    ]

    results = engine.run_baselines(task_id="media.intent", dataset_id="snap_123", examples=examples)
    assert len(results) == 3

    backends = {r.backend for r in results}
    assert backends == {"rule", "prompt", "decision"}

    rule_res = next(r for r in results if r.backend == "rule")
    assert rule_res.latency_p95_ms >= 0.0
    assert rule_res.memory_mb == 16.0

    decision_res = next(r for r in results if r.backend == "decision")
    assert decision_res.latency_p95_ms <= 10.0
    assert decision_res.memory_mb == 32.0


def test_custom_rule_evaluator():
    evaluator = RuleBaselineEvaluator(rules={"turn on": "media_play"})
    examples = [
        {"input": "please turn on the tv", "output": "media_play"},
        {"input": "stop music", "output": "media_stop"},
    ]
    res = evaluator.evaluate(task_id="test.task", dataset_id="snap_456", examples=examples)
    assert res.metrics["accuracy"] == 0.5
    assert res.output_validity == 0.5
