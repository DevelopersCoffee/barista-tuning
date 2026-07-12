from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from slm_train_eval_publish.config import load_config

app = typer.Typer(help="Train, evaluate, and publish small language models.")
console = Console()


@app.command()
def compile(
    ddl: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("build"),
) -> None:
    """Compile a domain DDL file into Domain IR and Phase 1 artifacts."""
    from slm_train_eval_publish.compiler import compile_domain

    result = compile_domain(ddl, output)
    console.print(f"Compiled domain artifacts: {result.root}")
    console.print(f"Domain IR: {result.domain_ir}")
    console.print(f"Compiler manifest: {result.compiler_manifest}")


@app.command("generate-media-actions")
def generate_media_actions(
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "data/processed/airo_media_actions_train.jsonl"
    ),
    count: Annotated[int, typer.Option("--count", "-n", min=1)] = 1000,
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """Generate Airo TV Media Actions SFT examples."""
    from slm_train_eval_publish.media_actions import write_media_actions_jsonl

    path = write_media_actions_jsonl(output=output, count=count, seed=seed)
    console.print(f"Generated {count} media action examples: {path}")


@app.command("generate-media-action-splits")
def generate_media_action_splits(
    train_output: Annotated[Path, typer.Option("--train-output")] = Path(
        "data/processed/airo_media_actions_train.jsonl"
    ),
    eval_output: Annotated[Path, typer.Option("--eval-output")] = Path(
        "data/processed/airo_media_actions_eval.jsonl"
    ),
    train_count: Annotated[int, typer.Option("--train-count", min=1)] = 5000,
    eval_count: Annotated[int, typer.Option("--eval-count", min=1)] = 500,
    seed: Annotated[int, typer.Option("--seed")] = 42,
) -> None:
    """Generate deterministic train/eval splits for Airo TV Media Actions."""
    from slm_train_eval_publish.media_actions import write_media_actions_split

    train_path, eval_path = write_media_actions_split(
        train_output=train_output,
        eval_output=eval_output,
        train_count=train_count,
        eval_count=eval_count,
        seed=seed,
    )
    console.print(f"Generated {train_count} train examples: {train_path}")
    console.print(f"Generated {eval_count} eval examples: {eval_path}")


@app.command("compile-iptv")
def compile_iptv(
    source: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("build/iptv-media-ir"),
    provider: Annotated[str, typer.Option("--provider")] = "iptv",
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
) -> None:
    """Compile IPTV JSON or M3U path/URL into Media IR v1 JSONL."""
    from slm_train_eval_publish.iptv_compiler import compile_iptv_source_to_media_ir

    result = compile_iptv_source_to_media_ir(
        source=source,
        output=output,
        provider=provider,
        limit=limit,
    )
    console.print(f"Compiled {result.asset_count} IPTV assets")
    console.print(f"Media IR: {result.media_ir}")
    console.print(f"Report: {result.report}")


@app.command("compile-media-pack")
def compile_media_pack(
    media_ir: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "packs/media.iptv.india-0.1.0.pack"
    ),
    pack_id: Annotated[str, typer.Option("--pack-id")] = "media.iptv.india",
    pack_name: Annotated[str, typer.Option("--pack-name")] = "India IPTV",
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    provider: Annotated[str, typer.Option("--provider")] = "iptv",
    compile_report: Annotated[Path | None, typer.Option("--compile-report")] = None,
) -> None:
    """Compile Media IR JSONL into a ZIP-based .pack artifact."""
    from slm_train_eval_publish.pack_compiler import compile_media_pack as compile_pack

    result = compile_pack(
        media_ir=media_ir,
        output=output,
        pack_id=pack_id,
        pack_name=pack_name,
        version=version,
        provider=provider,
        compile_report=compile_report,
    )
    console.print(f"Compiled media pack with {result.asset_count} assets: {result.pack_path}")


@app.command("compile-iptv-pack")
def compile_iptv_pack(
    source: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "packs/media.iptv.india-0.1.0.pack"
    ),
    work_dir: Annotated[Path, typer.Option("--work-dir")] = Path("build/iptv-media-ir"),
    pack_id: Annotated[str, typer.Option("--pack-id")] = "media.iptv.india",
    pack_name: Annotated[str, typer.Option("--pack-name")] = "India IPTV",
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    provider: Annotated[str, typer.Option("--provider")] = "iptv",
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
) -> None:
    """Compile IPTV JSON/M3U path/URL directly into a ZIP-based .pack artifact."""
    from slm_train_eval_publish.iptv_compiler import compile_iptv_source_to_media_ir
    from slm_train_eval_publish.pack_compiler import compile_media_pack as compile_pack

    media_result = compile_iptv_source_to_media_ir(
        source=source,
        output=work_dir,
        provider=provider,
        limit=limit,
    )
    pack_result = compile_pack(
        media_ir=media_result.media_ir,
        output=output,
        pack_id=pack_id,
        pack_name=pack_name,
        version=version,
        provider=provider,
        compile_report=media_result.report,
    )
    console.print(f"Compiled {media_result.asset_count} IPTV assets")
    console.print(f"Media IR: {media_result.media_ir}")
    console.print(f"Pack: {pack_result.pack_path}")


@app.command("eval-media-actions")
def eval_media_actions(
    dataset: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Evaluate the local rule-baseline media intent parser against JSONL examples."""
    import json

    from slm_train_eval_publish.media_intent import evaluate_media_actions_jsonl

    result = evaluate_media_actions_jsonl(dataset)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        console.print(f"Evaluation report: {output}")

    console.print(f"Total: {result['total']}")
    console.print(f"Intent accuracy: {result['intent_accuracy']:.3f}")
    console.print(f"Tool accuracy: {result['tool_accuracy']:.3f}")
    console.print(f"Constraint exact accuracy: {result['constraint_exact_accuracy']:.3f}")
    console.print(f"Clarification accuracy: {result['clarification_accuracy']:.3f}")


@app.command()
def train(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Fine-tune the configured base model."""
    from slm_train_eval_publish.train import train_model

    output_dir = train_model(load_config(config))
    console.print(f"Training complete: {output_dir}")


@app.command()
def evaluate(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Evaluate the configured model artifact."""
    from slm_train_eval_publish.evaluate import evaluate_model

    report_path = evaluate_model(load_config(config))
    console.print(f"Evaluation report written: {report_path}")


@app.command()
def publish(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Publish the configured model artifact to Hugging Face Hub."""
    from slm_train_eval_publish.publish import publish_model

    url = publish_model(load_config(config))
    console.print(f"Published model: {url}")


if __name__ == "__main__":
    app()
