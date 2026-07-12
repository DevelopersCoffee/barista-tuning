from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slm_train_eval_publish.compiler.artifacts import write_artifacts
from slm_train_eval_publish.compiler.ddl import load_domain_definition
from slm_train_eval_publish.compiler.ir import build_domain_ir
from slm_train_eval_publish.compiler.manifest import write_compiler_manifest
from slm_train_eval_publish.compiler.verify import verify_domain_ir


@dataclass(frozen=True)
class CompileResult:
    root: Path
    domain_ir: Path
    compiler_manifest: Path
    knowledge_pack: Path
    blueprint_pack: Path


def compile_domain(ddl_path: str | Path, output_dir: str | Path = "build") -> CompileResult:
    ddl = Path(ddl_path)
    output = Path(output_dir)

    definition = load_domain_definition(ddl)
    ir = build_domain_ir(definition)
    verification_errors = verify_domain_ir(ir)
    if verification_errors:
        message = "\n".join(f"- {error}" for error in verification_errors)
        raise ValueError(f"Domain IR verification failed:\n{message}")

    artifacts = write_artifacts(ir, output)
    manifest_path = write_compiler_manifest(
        ir=ir,
        ddl_path=ddl,
        output_root=output,
        artifacts=artifacts,
    )

    return CompileResult(
        root=Path(artifacts["root"]),
        domain_ir=Path(artifacts["domain_ir"]),
        compiler_manifest=manifest_path,
        knowledge_pack=Path(artifacts["knowledge_pack"]),
        blueprint_pack=Path(artifacts["blueprint_pack"]),
    )
