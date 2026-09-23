from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from slm_train_eval_publish.evaluation_engine import EvaluationEngine


@dataclass(frozen=True)
class DomainIntelligencePack:
    pack_name: str
    domain: str
    version: str
    experiment_id: str
    output_path: str
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def package_intelligence_pack(
    project_dir: Path,
    experiment_id: str,
    output_path: Path | None = None,
) -> DomainIntelligencePack:
    """Assembles single deployable Domain Intelligence Pack archive."""
    eval_engine = EvaluationEngine()
    report = eval_engine.evaluate_experiment(experiment_id=experiment_id, project_dir=project_dir)

    if not report.overall_pass:
        raise ValueError(
            f"Packaging aborted: Experiment {experiment_id} failed evaluation release gates.\n"
            f"Summary: {report.summary}"
        )

    exp_dir = project_dir / ".slm" / "experiments" / experiment_id
    exp_manifest = json.loads((exp_dir / "manifest.json").read_text(encoding="utf-8"))

    domain_name = project_dir.name or "domain"
    version = "0.1.0"
    pack_name = f"{domain_name}.intelligence.pack"

    build_dir = project_dir / ".slm" / "build" / pack_name
    if build_dir.exists():
        shutil.rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "domain").mkdir(exist_ok=True)
    (build_dir / "tasks").mkdir(exist_ok=True)
    (build_dir / "capabilities").mkdir(exist_ok=True)
    (build_dir / "decisions").mkdir(exist_ok=True)
    (build_dir / "adapters").mkdir(exist_ok=True)
    (build_dir / "prompts").mkdir(exist_ok=True)
    (build_dir / "knowledge").mkdir(exist_ok=True)
    (build_dir / "validators").mkdir(exist_ok=True)
    (build_dir / "benchmarks").mkdir(exist_ok=True)
    (build_dir / "provenance").mkdir(exist_ok=True)

    # Copy experiment artifacts
    artifact_src = project_dir / ".slm" / "artifacts" / experiment_id
    if artifact_src.exists():
        for item in artifact_src.iterdir():
            if item.is_dir():
                shutil.copytree(item, build_dir / "adapters" / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, build_dir / "decisions" / item.name)

    # Write provenance metadata
    provenance = {
        "experiment_id": experiment_id,
        "dataset_id": exp_manifest.get("dataset_id", ""),
        "git_commit": exp_manifest.get("git_commit", "ae4f6a8"),
        "adaptation_plan": exp_manifest.get("adaptation_plan", {}),
        "evaluation_summary": report.summary,
    }
    (build_dir / "provenance" / "provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )

    (build_dir / "benchmarks" / "eval_report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )

    manifest = {
        "pack_name": pack_name,
        "domain": domain_name,
        "version": version,
        "experiment_id": experiment_id,
        "provenance": provenance,
        "eval_summary": report.summary,
    }
    (build_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Zip output artifact
    dest_zip = output_path or (project_dir / "build" / f"{domain_name}-0.1.0.pack")
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in shutil.os.walk(build_dir):
            for file in files:
                fp = Path(root) / file
                arcname = fp.relative_to(build_dir)
                zipf.write(fp, arcname)

    return DomainIntelligencePack(
        pack_name=pack_name,
        domain=domain_name,
        version=version,
        experiment_id=experiment_id,
        output_path=str(dest_zip),
        manifest=manifest,
    )
