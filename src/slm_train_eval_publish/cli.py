from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from slm_train_eval_publish.config import load_config

app = typer.Typer(help="Model Adaptation & Domain Intelligence Platform.")
console = Console()


@app.command("init")
def init_project(
    name: Annotated[str, typer.Argument(help="Project directory name to scaffold.")],
    target_dir: Annotated[Path, typer.Option("--path", "-p")] = Path("."),
) -> None:
    """Scaffold standard SLM project structure (slm.yaml, data/, schema/, domain/)."""
    proj_path = target_dir / name
    proj_path.mkdir(parents=True, exist_ok=True)

    (proj_path / "data").mkdir(exist_ok=True)
    (proj_path / "schema").mkdir(exist_ok=True)
    (proj_path / "domain").mkdir(exist_ok=True)

    slm_yaml_content = f"""domain:
  name: {name}
  version: "0.1.0"

task:
  id: {name}.main_task
  type: decision
  capability: structured_decision

adaptation:
  strategy: auto

constraints:
  target_f1: 0.85
  max_latency_p95_ms: 50.0
"""
    (proj_path / "slm.yaml").write_text(slm_yaml_content, encoding="utf-8")
    (proj_path / "data" / "train.jsonl").write_text("", encoding="utf-8")
    (proj_path / "data" / "eval.jsonl").write_text("", encoding="utf-8")
    (proj_path / "schema" / "output.json").write_text("{\n}\n", encoding="utf-8")

    console.print(f"[bold green]Scaffolded SLM project at:[/bold green] {proj_path.resolve()}")


@app.command("doctor")
def doctor(
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
) -> None:
    """Run project health diagnostics, dataset checks, and adaptation strategy recommendation."""
    from slm_train_eval_publish.doctor import print_doctor_report, run_doctor

    report = run_doctor(project_dir.resolve())
    print_doctor_report(report)


@app.command("data-inspect")
def data_inspect(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    eval_file: Annotated[Path | None, typer.Option("--eval")] = None,
    schema_file: Annotated[Path | None, typer.Option("--schema")] = None,
) -> None:
    """Completely read-only audit of a dataset (duplicates, leakage, tokens, schema validity)."""
    from slm_train_eval_publish.dataset_engine import inspect_dataset

    profile = inspect_dataset(source_path=source, eval_path=eval_file, schema_path=schema_file)
    console.print(f"[bold cyan]Dataset Profile for {source.name}:[/bold cyan]")
    console.print(f"  Total Examples: {profile.total_examples}")
    console.print(f"  Valid Examples: {profile.valid_examples}")
    console.print(f"  Duplicates: {profile.duplicate_count}")
    console.print(f"  Exact Leakage: {profile.exact_leakage_count}")
    console.print(f"  Normalized Leakage: {profile.normalized_leakage_count}")
    console.print(f"  Schema Validity: {profile.schema_validity * 100:.1f}%")

    if profile.quality_warnings:
        console.print("\n[bold yellow]Quality Warnings:[/bold yellow]")
        for w in profile.quality_warnings:
            console.print(f"  • {w}")


@app.command("prepare")
def prepare(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("."),
    train_ratio: Annotated[float, typer.Option("--train-ratio")] = 0.8,
    val_ratio: Annotated[float, typer.Option("--val-ratio")] = 0.1,
    test_ratio: Annotated[float, typer.Option("--test-ratio")] = 0.1,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    leakage_policy: Annotated[str, typer.Option("--leakage-policy")] = "fail",
) -> None:
    """Generate an immutable DatasetSnapshot under .slm/datasets/<dataset_id>/."""
    from slm_train_eval_publish.dataset_engine import DatasetPreparationConfig, prepare_dataset

    cfg = DatasetPreparationConfig(
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
        leakage_policy=leakage_policy,
    )
    res = prepare_dataset(source_path=source, output_dir=output, config=cfg)
    console.print(f"[bold green]Created immutable DatasetSnapshot:[/bold green] {res['dataset_id']}")
    console.print(f"  Snapshot path: {res['snapshot_dir']}")


@app.command("baseline")
def baseline(
    source: Annotated[Path, typer.Argument(exists=True, readable=True)],
    task_id: Annotated[str, typer.Option("--task")] = "main_task",
) -> None:
    """Run pre-adaptation baselines (rule, prompt, decision) to establish benchmark starting point."""
    import json
    from slm_train_eval_publish.baseline import BaselineEngine

    lines = [json.loads(l) for l in source.read_text(encoding="utf-8").splitlines() if l.strip()]
    engine = BaselineEngine()
    results = engine.run_baselines(task_id=task_id, dataset_id="cli_base", examples=lines)

    console.print(f"[bold cyan]Baseline Benchmarks for task '{task_id}':[/bold cyan]")
    for r in results:
        f1 = r.metrics.get("f1", 0.0)
        console.print(
            f"  • [bold blue]{r.backend:<12}[/bold blue] | F1: {f1:.4f} | P95 Latency: {r.latency_p95_ms}ms | Memory: {r.memory_mb}MB"
        )


@app.command("plan")
def plan(
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
) -> None:
    """Display the evidence-driven AdaptationPlan compiled from task, dataset, and baseline results."""
    from slm_train_eval_publish.doctor import run_plan

    adaptation_plan = run_plan(project_dir=project_dir.resolve())
    console.print("[bold cyan]Compiled Adaptation Plan:[/bold cyan]")
    console.print(f"  Method: [bold green]{adaptation_plan.method}[/bold green]")
    console.print(f"  Backend: [bold blue]{adaptation_plan.backend}[/bold blue]")
    console.print("  Rationale:")
    for r in adaptation_plan.reasons:
        console.print(f"    • {r}")


@app.command("execute")
def execute_plan(
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
    snapshot_id: Annotated[str, typer.Option("--snapshot")] = "snap_default",
) -> None:
    """Execute the compiled AdaptationPlan, create artifact, and log immutable ExperimentRecord."""
    from slm_train_eval_publish.doctor import run_plan
    from slm_train_eval_publish.execution import ExecutionEngine

    proj = project_dir.resolve()
    adaptation_plan = run_plan(project_dir=proj)
    engine = ExecutionEngine()
    res = engine.execute(plan=adaptation_plan, project_dir=proj, snapshot_id=snapshot_id)

    console.print(f"[bold green]Executed Adaptation Plan![/bold green]")
    console.print(f"  Experiment ID: [bold cyan]{res.experiment_id}[/bold cyan]")
    console.print(f"  Artifact Path: {res.output_path}")
    console.print(f"  Execution Time: {res.execution_time_sec}s")


@app.command("eval-gate")
def evaluate_experiment(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID to evaluate.")],
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
    target_f1: Annotated[float, typer.Option("--target-f1")] = 0.85,
    max_latency_p95_ms: Annotated[float, typer.Option("--max-latency-p95")] = 100.0,
) -> None:
    """Run multi-dimensional evaluation gates (target task, regression, safety, P95 latency)."""
    from slm_train_eval_publish.evaluation_engine import EvaluationEngine, print_eval_report

    engine = EvaluationEngine()
    report = engine.evaluate_experiment(
        experiment_id=experiment_id,
        project_dir=project_dir.resolve(),
        target_f1=target_f1,
        max_latency_p95_ms=max_latency_p95_ms,
    )
    print_eval_report(report)


@app.command("compare")
def compare_runs(
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
) -> None:
    """Compare experiment run records for a project side-by-side."""
    from slm_train_eval_publish.experiment import ExperimentTracker, compare_experiments

    tracker = ExperimentTracker()
    records = tracker.list_experiments(project_dir.resolve())
    compare_experiments(records)


@app.command("package")
def package_pack(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID to package.")],
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
) -> None:
    """Assemble a single deployable Domain Intelligence Pack (.pack) archive."""
    from slm_train_eval_publish.packager import package_intelligence_pack

    pack = package_intelligence_pack(project_dir=project_dir.resolve(), experiment_id=experiment_id)
    console.print(f"[bold green]Successfully packaged Domain Intelligence Pack:[/bold green]")
    console.print(f"  Pack Name: [bold cyan]{pack.pack_name}[/bold cyan]")
    console.print(f"  Archive Path: {pack.output_path}")


@app.command("release")
def release_artifact(
    experiment_id: Annotated[str, typer.Argument(help="Experiment ID to release.")],
    project_dir: Annotated[Path, typer.Option("--project", "-p")] = Path("."),
) -> None:
    """Verify release gates and produce production release artifact."""
    from slm_train_eval_publish.evaluation_engine import EvaluationEngine
    from slm_train_eval_publish.packager import package_intelligence_pack

    proj = project_dir.resolve()
    eval_engine = EvaluationEngine()
    report = eval_engine.evaluate_experiment(experiment_id=experiment_id, project_dir=proj)

    if not report.overall_pass:
        console.print(f"[bold red]Release Rejected:[/bold red] {report.summary}")
        raise typer.Exit(code=1)

    pack = package_intelligence_pack(project_dir=proj, experiment_id=experiment_id)
    console.print(f"[bold green]RELEASE APPROVED![/bold green] Emitted production artifact:")
    console.print(f"  {pack.output_path}")




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


@app.command("compile-code-index")
def compile_code_index(
    export: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "build/code-index"
    ),
) -> None:
    """Compile a vendor-neutral code-index export into governed metadata."""
    from slm_train_eval_publish.code_index_ingestion import compile_code_index_export

    catalog = compile_code_index_export(export, output)
    console.print(f"Metadata catalog: {catalog}")


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


@app.command("generate-enterprise-knowledge-splits")
def generate_enterprise_knowledge_splits(
    catalog: Annotated[Path, typer.Argument(exists=True, readable=True)],
    train_output: Annotated[Path, typer.Option("--train-output")] = Path(
        "data/processed/enterprise_knowledge_train.jsonl"
    ),
    eval_output: Annotated[Path, typer.Option("--eval-output")] = Path(
        "data/processed/enterprise_knowledge_eval.jsonl"
    ),
    train_count: Annotated[int, typer.Option("--train-count", min=1)] = 5000,
    eval_count: Annotated[int, typer.Option("--eval-count", min=1)] = 500,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    instruction_mode: Annotated[
        str,
        typer.Option("--instruction-mode", help="Use 'basic' or 'blueprint'."),
    ] = "basic",
    augmentation_profile: Annotated[
        str,
        typer.Option(
            "--augmentation-profile",
            help="Use 'standard' or the stronger 'safety_v2' correction mix.",
        ),
    ] = "standard",
) -> None:
    """Generate governed enterprise-knowledge SFT train/eval splits."""
    from slm_train_eval_publish.enterprise_knowledge import (
        write_enterprise_knowledge_split,
    )

    train_path, eval_path = write_enterprise_knowledge_split(
        catalog_path=catalog,
        train_output=train_output,
        eval_output=eval_output,
        train_count=train_count,
        eval_count=eval_count,
        seed=seed,
        instruction_mode=instruction_mode,
        augmentation_profile=augmentation_profile,
    )
    console.print(f"Generated {train_count} train examples: {train_path}")
    console.print(f"Generated {eval_count} eval examples: {eval_path}")


@app.command("validate-enterprise-knowledge-data")
def validate_enterprise_knowledge_data(
    dataset: Annotated[Path, typer.Argument(exists=True, readable=True)],
    catalog: Annotated[
        Path,
        typer.Option("--catalog", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/metadata_catalog.json"),
) -> None:
    """Validate enterprise-knowledge SFT JSONL and structured action outputs."""
    from slm_train_eval_publish.enterprise_knowledge import (
        validate_enterprise_knowledge_jsonl,
    )

    row_count = validate_enterprise_knowledge_jsonl(dataset, catalog_path=catalog)
    console.print(f"Valid enterprise-knowledge dataset: {dataset}")
    console.print(f"Rows: {row_count}")


@app.command("generate-enterprise-knowledge-benchmark")
def generate_enterprise_knowledge_benchmark(
    benchmark_catalog: Annotated[Path, typer.Argument(exists=True, readable=True)],
    training_catalog: Annotated[
        Path,
        typer.Option("--training-catalog", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/metadata_catalog.json"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "data/processed/enterprise_knowledge_benchmark.jsonl"
    ),
    count: Annotated[int, typer.Option("--count", min=4)] = 100,
    seed: Annotated[int, typer.Option("--seed")] = 2026,
) -> None:
    """Generate a held-out enterprise-knowledge benchmark from a disjoint catalog."""
    from slm_train_eval_publish.enterprise_knowledge_evaluation import (
        write_enterprise_knowledge_benchmark,
    )

    path = write_enterprise_knowledge_benchmark(
        benchmark_catalog_path=benchmark_catalog,
        training_catalog_path=training_catalog,
        output=output,
        count=count,
        seed=seed,
    )
    console.print(f"Generated {count} held-out benchmark examples: {path}")


@app.command("predict-enterprise-knowledge")
def predict_enterprise_knowledge(
    dataset: Annotated[Path, typer.Argument(exists=True, readable=True)],
    model: Annotated[str, typer.Argument(help="Hugging Face model ID or local model path.")],
    catalog: Annotated[
        Path,
        typer.Option("--catalog", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/benchmark_catalog.json"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "reports/enterprise_knowledge_predictions.jsonl"
    ),
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    max_new_tokens: Annotated[int, typer.Option("--max-new-tokens", min=1)] = 512,
    prompt_mode: Annotated[
        str,
        typer.Option(
            "--prompt-mode",
            help="Use 'blueprint' for base models or 'sft' for adapters.",
        ),
    ] = "blueprint",
    backend: Annotated[
        str,
        typer.Option("--backend", help="Use 'auto', 'transformers', or 'mlx'."),
    ] = "auto",
) -> None:
    """Generate validated enterprise-knowledge predictions from a model."""
    from slm_train_eval_publish.enterprise_knowledge_evaluation import (
        predict_enterprise_knowledge_with_model,
    )

    console.print(f"Loading model: {model}")
    path = predict_enterprise_knowledge_with_model(
        dataset=dataset,
        model_name_or_path=model,
        catalog_path=catalog,
        output=output,
        limit=limit,
        max_new_tokens=max_new_tokens,
        prompt_mode=prompt_mode,
        backend=backend,
    )
    console.print(f"Prediction JSONL: {path}")


@app.command("score-enterprise-knowledge")
def score_enterprise_knowledge(
    benchmark: Annotated[Path, typer.Argument(exists=True, readable=True)],
    predictions: Annotated[Path, typer.Argument(exists=True, readable=True)],
    catalog: Annotated[
        Path,
        typer.Option("--catalog", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/benchmark_catalog.json"),
    requirements: Annotated[
        Path,
        typer.Option("--requirements", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/requirements.yaml"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "reports/enterprise_knowledge_report.json"
    ),
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    fail_on_requirements: Annotated[
        bool,
        typer.Option("--fail-on-requirements"),
    ] = False,
) -> None:
    """Score enterprise predictions and evaluate release requirements."""
    import json

    from slm_train_eval_publish.enterprise_knowledge_evaluation import (
        score_enterprise_knowledge_predictions,
    )

    report = score_enterprise_knowledge_predictions(
        expected_path=benchmark,
        predictions_path=predictions,
        catalog_path=catalog,
        requirements_path=requirements,
        limit=limit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    console.print(f"Evaluation report: {output}")
    for name, value in report["metrics"].items():
        console.print(f"{name}: {value:.3f}")
    verdict = "PASS" if report["requirements"]["passed"] else "FAIL"
    console.print(f"Requirements: {verdict}")
    if fail_on_requirements and not report["requirements"]["passed"]:
        raise typer.Exit(1)


@app.command("analyze-enterprise-knowledge-errors")
def analyze_enterprise_knowledge_errors_command(
    expected: Annotated[Path, typer.Argument(exists=True, readable=True)],
    predictions: Annotated[Path, typer.Argument(exists=True, readable=True)],
    catalog: Annotated[
        Path,
        typer.Option("--catalog", exists=True, readable=True),
    ] = Path("examples/enterprise_knowledge/benchmark_catalog.json"),
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "reports/enterprise_knowledge_error_analysis.json"
    ),
    max_examples: Annotated[int, typer.Option("--max-examples", min=0)] = 3,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
) -> None:
    """Classify overlapping schema, semantic, grounding, and safety errors."""
    from slm_train_eval_publish.enterprise_knowledge_error_analysis import (
        analyze_enterprise_knowledge_errors,
    )

    report = analyze_enterprise_knowledge_errors(
        expected_path=expected,
        predictions_path=predictions,
        catalog_path=catalog,
        output_path=output,
        max_examples_per_category=max_examples,
        limit=limit,
    )
    console.print(f"Error analysis: {output}")
    console.print(f"Rows: {report['total']}")


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


@app.command("validate-media-pack")
def validate_media_pack(
    pack_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
) -> None:
    """Validate a ZIP-based media .pack before installing it on device."""
    from slm_train_eval_publish.pack_validator import validate_media_pack as validate_pack

    result = validate_pack(pack_path)
    if result.valid:
        pack_id = (result.manifest or {}).get("pack", {}).get("id", "unknown")
        console.print(f"Valid media pack: {pack_id}")
        console.print(f"Assets: {result.asset_count}")
        return

    console.print(f"Invalid media pack: {pack_path}")
    for error in result.errors:
        console.print(f"- {error}")
    raise typer.Exit(1)


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


@app.command("compare-media-action-predictions")
def compare_media_action_predictions(
    dataset: Annotated[Path, typer.Argument(exists=True, readable=True)],
    predictions: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Compare SLM media-action predictions against labels and the rule baseline."""
    import json

    from slm_train_eval_publish.media_intent import evaluate_media_action_predictions_jsonl

    result = evaluate_media_action_predictions_jsonl(dataset, predictions)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        console.print(f"Comparison report: {output}")

    console.print(f"Total: {result['total']}")
    console.print(f"Rule intent accuracy: {result['rule']['intent_accuracy']:.3f}")
    console.print(f"SLM intent accuracy: {result['slm']['intent_accuracy']:.3f}")
    console.print(
        "SLM constraint exact accuracy: "
        f"{result['slm']['constraint_exact_accuracy']:.3f}"
    )


@app.command("predict-media-actions")
def predict_media_actions(
    dataset: Annotated[Path, typer.Argument(exists=True, readable=True)],
    model_path: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path(
        "reports/airo_media_actions_slm_predictions.jsonl"
    ),
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    max_new_tokens: Annotated[int, typer.Option("--max-new-tokens", min=1)] = 128,
) -> None:
    """Generate media-action JSONL predictions from a local model or PEFT adapter."""
    from slm_train_eval_publish.media_action_predictions import (
        predict_media_actions_with_model,
    )

    path = predict_media_actions_with_model(
        dataset=dataset,
        model_path=model_path,
        output=output,
        limit=limit,
        max_new_tokens=max_new_tokens,
    )
    console.print(f"Prediction JSONL: {path}")


@app.command("package-edge-ffi-android")
def package_edge_ffi_android(
    airo_app: Annotated[
        Path,
        typer.Option(
            "--airo-app",
            help="Airo Flutter app root, for example /path/to/airo/app.",
        ),
    ],
    artifact: Annotated[
        list[str] | None,
        typer.Option(
            "--artifact",
            help="Prebuilt artifact in ABI=PATH format. Can be passed more than once.",
        ),
    ] = None,
    build: Annotated[
        bool,
        typer.Option("--build", help="Build Android artifacts with cargo-ndk before packaging."),
    ] = False,
    abi: Annotated[
        list[str] | None,
        typer.Option("--abi", help="Android ABI for --build. Can be passed more than once."),
    ] = None,
    release: Annotated[bool, typer.Option("--release/--debug")] = True,
) -> None:
    """Package Rust edge-ffi shared libraries into Airo Android jniLibs."""
    from slm_train_eval_publish.android_ffi_packager import (
        build_android_edge_ffi,
        package_android_edge_ffi,
        parse_abi_artifact,
    )

    if build:
        result = build_android_edge_ffi(
            repo_root=Path.cwd(),
            airo_app=airo_app,
            abis=abi or ["arm64-v8a"],
            release=release,
        )
    else:
        artifact_specs = artifact or []
        artifacts = dict(parse_abi_artifact(spec) for spec in artifact_specs)
        result = package_android_edge_ffi(airo_app=airo_app, artifacts=artifacts)

    console.print(f"jniLibs: {result.jni_libs_root}")
    for packaged_abi, path in sorted(result.copied.items()):
        console.print(f"{packaged_abi}: {path}")


@app.command()
def train(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Fine-tune the configured base model."""
    from slm_train_eval_publish.train import train_model

    output_dir = train_model(load_config(config))
    console.print(f"Training complete: {output_dir}")


@app.command("package-training-job")
def package_training_job_command(
    config: Annotated[Path, typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
) -> None:
    """Package local training inputs for a provider-neutral remote runner."""
    from slm_train_eval_publish.training_job import package_training_job

    job_dir = package_training_job(config, output)
    console.print(f"Portable training job: {job_dir}")


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
