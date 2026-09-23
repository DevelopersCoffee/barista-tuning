from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from slm_train_eval_publish.adaptation_planner import (
    AdaptationPlan,
    AdaptationPlanner,
    Constraints,
    HardwareProfile,
    PlannerContext,
)
from slm_train_eval_publish.baseline import BaselineEngine, BaselineResult
from slm_train_eval_publish.dataset_engine import DatasetProfile, inspect_dataset

console = Console()


def run_plan(
    project_dir: Path,
    source_path: Path | None = None,
    eval_path: Path | None = None,
    schema_path: Path | None = None,
    task_kind: str = "decision",
    capability_id: str = "structured_decision",
) -> AdaptationPlan:
    """Orchestrates Phase A -> Phase C -> Phase B into a single compiled AdaptationPlan."""
    src = source_path or (project_dir / "data" / "train.jsonl")
    ev = eval_path or (project_dir / "data" / "eval.jsonl")
    sch = schema_path or (project_dir / "schema" / "output.json")

    if not src.exists():
        # Fallback dummy profile if train file does not exist yet
        profile = DatasetProfile(
            total_examples=0,
            valid_examples=0,
            invalid_examples=0,
            duplicate_count=0,
            exact_leakage_count=0,
            normalized_leakage_count=0,
            input_tokens=None,  # type: ignore
            output_tokens=None,  # type: ignore
            class_distribution={},
            schema_validity=0.0,
        )
    else:
        profile = inspect_dataset(source_path=src, eval_path=ev if ev.exists() else None, schema_path=sch if sch.exists() else None)

    # Run pre-adaptation baseline checks if dataset exists
    baselines: list[BaselineResult] = []
    if src.exists() and profile.valid_examples > 0:
        lines = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        engine = BaselineEngine()
        baselines = engine.run_baselines(task_id="project_task", dataset_id="baseline_snap", examples=lines)

    hw = HardwareProfile.auto_detect()
    ctx = PlannerContext(
        task_id="project_task",
        task_kind=task_kind,
        capability_id=capability_id,
        dataset_profile=profile,
        baselines=baselines,
        hardware=hw,
        constraints=Constraints(),
    )

    return AdaptationPlanner.resolve(ctx)


def run_doctor(project_dir: Path) -> dict[str, Any]:
    """Orchestrates project health diagnostics, snapshot verification, hardware inspection, and adaptation plan."""
    health_checks: list[dict[str, Any]] = []

    slm_yaml = project_dir / "slm.yaml"
    domain_yaml = project_dir / "domain" / "domain.yaml"

    if slm_yaml.exists() or domain_yaml.exists():
        health_checks.append({"name": "Domain Specification", "status": "PASS", "detail": "Domain spec found."})
    else:
        health_checks.append(
            {"name": "Domain Specification", "status": "WARN", "detail": "No slm.yaml or domain.yaml found."}
        )

    train_file = project_dir / "data" / "train.jsonl"
    eval_file = project_dir / "data" / "eval.jsonl"
    schema_file = project_dir / "schema" / "output.json"

    profile: DatasetProfile | None = None
    if train_file.exists():
        profile = inspect_dataset(source_path=train_file, eval_path=eval_file if eval_file.exists() else None, schema_path=schema_file if schema_file.exists() else None)
        health_checks.append(
            {
                "name": "Dataset Health",
                "status": "PASS" if not profile.quality_warnings else "WARN",
                "detail": f"{profile.total_examples} examples (schema validity: {profile.schema_validity * 100:.1f}%).",
            }
        )
    else:
        health_checks.append(
            {"name": "Dataset Health", "status": "WARN", "detail": "data/train.jsonl not found."}
        )

    plan = run_plan(project_dir=project_dir)

    return {
        "project_dir": str(project_dir),
        "health_checks": health_checks,
        "dataset_profile": profile.to_dict() if profile else None,
        "adaptation_plan": plan.to_dict(),
    }


def print_doctor_report(report: dict[str, Any]) -> None:
    """Renders formatted Rich console output for slm doctor."""
    console.print(Panel("[bold cyan]SLM Doctor Diagnostics[/bold cyan]", expand=False))

    tbl = Table(show_header=True, header_style="bold magenta")
    tbl.add_column("Check")
    tbl.add_column("Status")
    tbl.add_column("Detail")

    for chk in report["health_checks"]:
        st = chk["status"]
        color = "green" if st == "PASS" else ("yellow" if st == "WARN" else "red")
        tbl.add_row(chk["name"], f"[{color}]{st}[/{color}]", chk["detail"])

    console.print(tbl)

    plan = report["adaptation_plan"]
    console.print("\n[bold yellow]Recommended Adaptation Plan:[/bold yellow]")
    console.print(f"  Method: [bold green]{plan['method']}[/bold green]")
    console.print(f"  Backend: [bold blue]{plan['backend']}[/bold blue]")
    console.print("  Rationale:")
    for r in plan["reasons"]:
        console.print(f"    • {r}")
