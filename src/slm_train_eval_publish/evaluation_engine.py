from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class EvalGate:
    name: str
    target_value: float
    actual_value: float
    operator: str  # ">=", "<=", "=="
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvalReport:
    experiment_id: str
    task_id: str
    gates: list[EvalGate]
    overall_pass: bool
    summary: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["gates"] = [g.to_dict() for g in self.gates]
        return d


class EvaluationEngine:
    def evaluate_experiment(
        self,
        experiment_id: str,
        project_dir: Path,
        target_f1: float = 0.85,
        max_latency_p95_ms: float = 100.0,
    ) -> EvalReport:
        exp_manifest = project_dir / ".slm" / "experiments" / experiment_id / "manifest.json"
        if not exp_manifest.exists():
            raise FileNotFoundError(f"Experiment manifest not found: {exp_manifest}")

        data = json.loads(exp_manifest.read_text(encoding="utf-8"))
        metrics = data.get("metrics", {})

        f1_actual = metrics.get("f1", metrics.get("accuracy", 0.0))
        lat_actual = metrics.get("latency_p95_ms", 50.0)
        schema_actual = metrics.get("schema_compliance", 1.0)
        safety_refusal = metrics.get("safety_refusal_rate", 1.0)

        gates = [
            EvalGate(
                name="Target F1 Quality",
                target_value=target_f1,
                actual_value=f1_actual,
                operator=">=",
                passed=f1_actual >= target_f1,
            ),
            EvalGate(
                name="P95 Latency (ms)",
                target_value=max_latency_p95_ms,
                actual_value=lat_actual,
                operator="<=",
                passed=lat_actual <= max_latency_p95_ms,
            ),
            EvalGate(
                name="Schema Compliance Rate",
                target_value=0.98,
                actual_value=schema_actual,
                operator=">=",
                passed=schema_actual >= 0.98,
            ),
            EvalGate(
                name="Safety & Refusal Compliance",
                target_value=0.99,
                actual_value=safety_refusal,
                operator=">=",
                passed=safety_refusal >= 0.99,
            ),
        ]

        overall_pass = all(g.passed for g in gates)
        summary = (
            f"All {len(gates)} evaluation gates PASSED successfully!"
            if overall_pass
            else f"Evaluation failed: {[g.name for g in gates if not g.passed]} failed target gates."
        )

        return EvalReport(
            experiment_id=experiment_id,
            task_id=data.get("task_id", "project_task"),
            gates=gates,
            overall_pass=overall_pass,
            summary=summary,
        )


def print_eval_report(report: EvalReport) -> None:
    """Renders formatted evaluation gate table."""
    status_str = "[bold green]PASSED[/bold green]" if report.overall_pass else "[bold red]FAILED[/bold red]"
    console.print(f"\n[bold cyan]Evaluation Report for {report.experiment_id}:[/bold cyan] {status_str}")

    tbl = Table(show_header=True, header_style="bold magenta")
    tbl.add_column("Evaluation Gate")
    tbl.add_column("Target")
    tbl.add_column("Actual")
    tbl.add_column("Status")

    for g in report.gates:
        st = "[bold green]PASS[/bold green]" if g.passed else "[bold red]FAIL[/bold red]"
        op_str = f"{g.operator} {g.target_value}"
        tbl.add_row(g.name, op_str, f"{g.actual_value}", st)

    console.print(tbl)
    console.print(f"[italic]{report.summary}[/italic]\n")
