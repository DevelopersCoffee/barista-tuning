from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from slm_train_eval_publish import __version__
from slm_train_eval_publish.compiler.ir import DomainIR


def write_compiler_manifest(
    *,
    ir: DomainIR,
    ddl_path: Path,
    output_root: Path,
    artifacts: dict[str, str],
) -> Path:
    manifest = {
        "compiler": {
            "name": "domain-intelligence-compiler",
            "version": __version__,
        },
        "knowledge_pack": {
            "id": ir.domain,
            "version": ir.version,
        },
        "ddl": {
            "path": str(ddl_path),
            "sha256": _sha256(ddl_path),
        },
        "domain_ir": {
            "version": ir.ir_version,
            "path": artifacts["domain_ir"],
        },
        "artifacts": {
            "knowledge_pack": artifacts["knowledge_pack"],
            "blueprint_pack": artifacts["blueprint_pack"],
            "adapter": None,
            "runtime": None,
        },
        "build": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
        },
    }
    manifest_path = output_root / ir.domain / ir.version / "compiler_manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return manifest_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()
