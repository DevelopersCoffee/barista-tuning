from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class ExperimentRecord:
    id: str
    dataset_id: str
    adaptation_plan: dict[str, Any]
    metrics: dict[str, float]
    git_commit: str = "local"
    base_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    hardware: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    def __init__(self, experiments_dir: Path | None = None) -> None:
        self.experiments_dir = experiments_dir

    def _get_dir(self, project_dir: Path) -> Path:
        exp_dir = self.experiments_dir or (project_dir / ".slm" / "experiments")
        exp_dir.mkdir(parents=True, exist_ok=True)
        return exp_dir

    def log_experiment(self, record: ExperimentRecord, project_dir: Path) -> Path:
        exp_dir = self._get_dir(project_dir) / record.id
        exp_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = exp_dir / "manifest.json"
        data = record.to_dict()
        if not data["created_at"]:
            data["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        manifest_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return manifest_file

    def list_experiments(self, project_dir: Path) -> list[ExperimentRecord]:
        exp_dir = self._get_dir(project_dir)
        records: list[ExperimentRecord] = []
        if not exp_dir.exists():
            return records

        for item in sorted(exp_dir.iterdir()):
            if item.is_dir():
                mf = item / "manifest.json"
                if mf.exists():
                    try:
                        data = json.loads(mf.read_text(encoding="utf-8"))
                        records.append(
                            ExperimentRecord(
                                id=data["id"],
                                dataset_id=data.get("dataset_id", ""),
                                adaptation_plan=data.get("adaptation_plan", {}),
                                metrics=data.get("metrics", {}),
                                git_commit=data.get("git_commit", "local"),
                                base_model=data.get("base_model", ""),
                                hyperparameters=data.get("hyperparameters", {}),
                                hardware=data.get("hardware", {}),
                                provenance=data.get("provenance", {}),
                                created_at=data.get("created_at", ""),
                            )
                        )
                    except Exception:
                        continue
        return records


def compare_experiments(records: list[ExperimentRecord]) -> str:
    """Renders formatted comparison table of experiment runs."""
    if not records:
        return "No experiment records found for comparison."

    tbl = Table(title="Experiment Runs Comparison", show_header=True, header_style="bold cyan")
    tbl.add_column("Experiment ID")
    tbl.add_column("Method")
    tbl.add_column("Backend")
    tbl.add_column("Accuracy / F1")
    tbl.add_column("P95 Latency")
    tbl.add_column("Memory MB")
    tbl.add_column("Created At")

    for r in records:
        plan = r.adaptation_plan
        method = plan.get("method", "unknown")
        backend = plan.get("backend", "unknown")
        f1 = r.metrics.get("f1", r.metrics.get("accuracy", 0.0))
        p95 = r.metrics.get("latency_p95_ms", 0.0)
        mem = r.metrics.get("memory_mb", 0.0)
        created = r.created_at or "N/A"

        tbl.add_row(
            r.id,
            method,
            backend,
            f"{f1:.4f}",
            f"{p95:.1f}ms",
            f"{mem:.1f}MB",
            created,
        )

    console.print(tbl)
    return f"Compared {len(records)} experiments."
