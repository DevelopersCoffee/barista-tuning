from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from slm_train_eval_publish.config import load_config


def package_training_job(config_path: str | Path, output: str | Path) -> Path:
    source_config = Path(config_path).resolve()
    config = load_config(source_config)
    output_dir = Path(output).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Training job directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    data_dir.mkdir()

    raw = yaml.safe_load(source_config.read_text())
    data = raw.setdefault("data", {})
    if data.get("dataset_name"):
        raise ValueError("Portable job packaging currently requires local dataset files")

    _copy_input(data, "train_path", data_dir / "train.jsonl", source_config)
    if data.get("eval_path"):
        _copy_input(data, "eval_path", data_dir / "eval.jsonl", source_config)
    if data.get("validation_context_path"):
        _copy_input(
            data,
            "validation_context_path",
            data_dir / "context.json",
            source_config,
        )

    training = raw.setdefault("training", {})
    training["output_dir"] = "output/model"
    evaluation = raw.get("eval")
    if isinstance(evaluation, dict):
        evaluation["model_path"] = "output/model"
        evaluation["output_dir"] = "output/reports"
    publish = raw.get("publish")
    if isinstance(publish, dict):
        publish["model_dir"] = "output/model"

    bundled_config = output_dir / "config.yaml"
    bundled_config.write_text(yaml.safe_dump(raw, sort_keys=False))
    input_paths = [bundled_config, *sorted(data_dir.iterdir())]
    manifest = {
        "schema_version": 1,
        "backend": config.training.backend,
        "install_extra": "mlx" if config.training.backend == "mlx" else "train",
        "command": ["slm", "train", "config.yaml"],
        "source_config": source_config.name,
        "inputs": [
            {
                "path": str(path.relative_to(output_dir)),
                "sha256": _sha256(path),
            }
            for path in input_paths
        ],
    }
    (output_dir / "job.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return output_dir


def _copy_input(
    data: dict[str, Any],
    field: str,
    destination: Path,
    config_path: Path,
) -> None:
    source = _resolve_input(Path(str(data[field])), config_path)
    shutil.copy2(source, destination)
    data[field] = str(destination.relative_to(destination.parent.parent))


def _resolve_input(path: Path, config_path: Path) -> Path:
    if path.is_absolute():
        resolved = path
    elif path.exists():
        resolved = path.resolve()
    else:
        resolved = (config_path.parent / path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Training input not found: {path}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
