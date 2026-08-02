from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from slm_train_eval_publish.enterprise_knowledge import (
    INTENTS,
    EnterpriseKnowledgeExample,
    enterprise_knowledge_blueprint_instruction,
    generate_enterprise_knowledge_examples,
    validate_enterprise_action,
    validate_enterprise_knowledge_jsonl,
    validate_metadata_catalog,
)
from slm_train_eval_publish.structured_output import extract_first_json_object

BENCHMARK_FAMILIES = [
    "metadata_lookup",
    "grounded_answer",
    "live_data_lookup",
    "abstain",
]


def enterprise_knowledge_prompt(
    row: dict[str, Any],
    *,
    instruction_override: str | None = None,
) -> str:
    instruction = str(instruction_override or row.get("instruction", "")).strip()
    input_text = str(row.get("input", "")).strip()
    if not instruction or not input_text:
        raise ValueError("enterprise knowledge rows require instruction and input fields")
    return (
        "### Instruction\n"
        f"{instruction}\n\n"
        "### Input\n"
        f"{input_text}\n\n"
        "### Response\n"
    )


def parse_enterprise_knowledge_completion(
    completion: str,
    *,
    approved_tool_ids: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    json_text = extract_first_json_object(completion)
    if json_text is None:
        return None, "no JSON object found"
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as error:
        return None, f"invalid JSON: {error.msg}"
    if not isinstance(payload, dict):
        return None, "JSON payload is not an object"
    try:
        validate_enterprise_action(payload, approved_tool_ids=approved_tool_ids)
    except ValueError as error:
        return payload, str(error)
    return payload, None


def validate_catalog_isolation(
    training_catalog: dict[str, Any],
    benchmark_catalog: dict[str, Any],
) -> None:
    validate_metadata_catalog(training_catalog)
    validate_metadata_catalog(benchmark_catalog)

    identity_fields = {
        "entity IDs": ("entities", "entity_id"),
        "evidence IDs": ("evidence", "evidence_id"),
        "tool IDs": ("approved_tools", "tool_id"),
    }
    for label, (collection, field) in identity_fields.items():
        training_ids = {item[field] for item in training_catalog[collection]}
        benchmark_ids = {item[field] for item in benchmark_catalog[collection]}
        overlap = sorted(training_ids & benchmark_ids)
        if overlap:
            raise ValueError(f"training and benchmark {label} overlap: {overlap}")


def write_enterprise_knowledge_benchmark(
    *,
    benchmark_catalog_path: Path,
    training_catalog_path: Path,
    output: Path,
    count: int,
    seed: int = 42,
) -> Path:
    if count < 4:
        raise ValueError("benchmark count must be >= 4 to cover all intents")
    training_catalog = json.loads(training_catalog_path.read_text(encoding="utf-8"))
    benchmark_catalog = json.loads(benchmark_catalog_path.read_text(encoding="utf-8"))
    validate_catalog_isolation(training_catalog, benchmark_catalog)

    candidates = generate_enterprise_knowledge_examples(
        benchmark_catalog,
        max(count * 50, 400),
        seed,
    )
    examples = _select_balanced_unique_examples(candidates, count)
    intents = {example.family for example in examples}
    if intents != INTENTS:
        raise ValueError(f"benchmark does not cover every intent: {sorted(intents)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_sft_row(), ensure_ascii=False))
            handle.write("\n")
    return output


def _select_balanced_unique_examples(
    candidates: list[EnterpriseKnowledgeExample],
    count: int,
) -> list[EnterpriseKnowledgeExample]:
    targets = {
        family: count // len(BENCHMARK_FAMILIES)
        + (index < count % len(BENCHMARK_FAMILIES))
        for index, family in enumerate(BENCHMARK_FAMILIES)
    }
    unique_by_family: dict[str, list[EnterpriseKnowledgeExample]] = {
        family: [] for family in BENCHMARK_FAMILIES
    }
    seen: set[str] = set()
    for example in candidates:
        row_key = json.dumps(example.to_sft_row(), sort_keys=True)
        if row_key in seen:
            continue
        seen.add(row_key)
        unique_by_family[example.family].append(example)

    for family, target in targets.items():
        available = len(unique_by_family[family])
        if available < target:
            raise ValueError(
                f"benchmark needs {target} unique {family} examples but only "
                f"{available} are available"
            )

    selected: list[EnterpriseKnowledgeExample] = []
    max_target = max(targets.values())
    for index in range(max_target):
        for family in BENCHMARK_FAMILIES:
            if index < targets[family]:
                selected.append(unique_by_family[family][index])
    return selected


def predict_enterprise_knowledge_with_model(
    *,
    dataset: Path,
    model_name_or_path: str,
    catalog_path: Path,
    output: Path,
    limit: int | None = None,
    max_new_tokens: int = 512,
    prompt_mode: str = "blueprint",
    backend: str = "auto",
) -> Path:
    validate_enterprise_knowledge_jsonl(dataset, catalog_path=catalog_path)
    rows = _read_jsonl(dataset)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        rows = rows[:limit]
    if not rows:
        raise ValueError("benchmark has no rows to predict")

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate_metadata_catalog(catalog)
    approved_tool_ids = {tool["tool_id"] for tool in catalog["approved_tools"]}
    if prompt_mode not in {"blueprint", "sft"}:
        raise ValueError("prompt_mode must be 'blueprint' or 'sft'")
    instruction_override = (
        enterprise_knowledge_blueprint_instruction(catalog)
        if prompt_mode == "blueprint"
        else None
    )

    selected_backend = detect_prediction_backend(model_name_or_path, requested=backend)
    generate_completion = _build_completion_generator(
        model_name_or_path,
        selected_backend,
        max_new_tokens=max_new_tokens,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            prompt = enterprise_knowledge_prompt(
                row,
                instruction_override=instruction_override,
            )
            completion = generate_completion(prompt)
            payload, error = parse_enterprise_knowledge_completion(
                completion,
                approved_tool_ids=approved_tool_ids,
            )
            handle.write(
                json.dumps(
                    {
                        "input": row["input"],
                        "output": payload,
                        "raw_completion": completion,
                        "parse_error": error,
                        "prompt_mode": prompt_mode,
                        "backend": selected_backend,
                    },
                    ensure_ascii=False,
                )
            )
            handle.write("\n")
            handle.flush()

    return output


def detect_prediction_backend(model_name_or_path: str, *, requested: str = "auto") -> str:
    if requested not in {"auto", "transformers", "mlx"}:
        raise ValueError("backend must be 'auto', 'transformers', or 'mlx'")
    if requested != "auto":
        return requested
    adapter_config_path = Path(model_name_or_path) / "adapter_config.json"
    if adapter_config_path.is_file():
        adapter_config = json.loads(adapter_config_path.read_text(encoding="utf-8"))
        if "fine_tune_type" in adapter_config and "model" in adapter_config:
            return "mlx"
    return "transformers"


def _build_completion_generator(
    model_name_or_path: str,
    backend: str,
    *,
    max_new_tokens: int,
) -> Callable[[str], str]:
    if backend == "mlx":
        from mlx_lm import generate, load

        adapter_config_path = Path(model_name_or_path) / "adapter_config.json"
        if not adapter_config_path.is_file():
            raise ValueError("MLX prediction requires an adapter directory")
        adapter_config = json.loads(adapter_config_path.read_text(encoding="utf-8"))
        base_model = adapter_config.get("model")
        if not isinstance(base_model, str) or not base_model:
            raise ValueError("MLX adapter config is missing its base model")
        model, tokenizer = load(base_model, adapter_path=model_name_or_path)

        def generate_with_mlx(prompt: str) -> str:
            return generate(
                model,
                tokenizer,
                prompt=prompt,
                verbose=False,
                max_tokens=max_new_tokens,
            ).strip()

        return generate_with_mlx

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_path = Path(model_name_or_path)
    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    if model_path.is_dir() and (model_path / "adapter_config.json").exists():
        from peft import AutoPeftModelForCausalLM

        model = AutoPeftModelForCausalLM.from_pretrained(
            model_name_or_path,
            torch_dtype="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            torch_dtype="auto",
        )
    device = _best_torch_device(torch)
    model.to(device)
    model.eval()

    def generate_with_transformers(prompt: str) -> str:
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=1536,
        ).to(device)
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        prompt_token_count = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0][prompt_token_count:]
        return tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    return generate_with_transformers


def score_enterprise_knowledge_predictions(
    *,
    expected_path: Path,
    predictions_path: Path,
    catalog_path: Path,
    requirements_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    expected_rows = _read_jsonl(expected_path)
    prediction_rows = _read_jsonl(predictions_path)
    if not expected_rows:
        raise ValueError("expected benchmark has no rows")
    benchmark_total = len(expected_rows)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        expected_rows = expected_rows[:limit]
        prediction_rows = prediction_rows[:limit]
    if len(expected_rows) != len(prediction_rows):
        raise ValueError(
            "prediction count does not match benchmark: "
            f"{len(prediction_rows)} != {len(expected_rows)}"
        )

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    validate_metadata_catalog(catalog)
    approved_tool_ids = {tool["tool_id"] for tool in catalog["approved_tools"]}

    expected_actions: list[dict[str, Any]] = []
    predicted_actions: list[dict[str, Any] | None] = []
    schema_valid: list[bool] = []
    for index, (expected_row, prediction_row) in enumerate(
        zip(expected_rows, prediction_rows, strict=True),
        start=1,
    ):
        if prediction_row.get("input") != expected_row.get("input"):
            raise ValueError(f"prediction row {index} input does not match benchmark")
        expected_action = _parse_expected_action(expected_row, index, approved_tool_ids)
        predicted_action = prediction_row.get("output")
        if predicted_action is not None and not isinstance(predicted_action, dict):
            raise ValueError(f"prediction row {index} output must be an object or null")
        expected_actions.append(expected_action)
        predicted_actions.append(predicted_action)
        schema_valid.append(_is_schema_valid(predicted_action, approved_tool_ids))

    metrics = _calculate_metrics(
        expected_actions,
        predicted_actions,
        schema_valid,
        approved_tool_ids,
    )
    requirements = yaml.safe_load(requirements_path.read_text(encoding="utf-8"))
    requirement_result = evaluate_requirements(metrics, requirements)
    return {
        "benchmark": str(expected_path),
        "predictions": str(predictions_path),
        "catalog": str(catalog_path),
        "requirements_file": str(requirements_path),
        "benchmark_total": benchmark_total,
        "total": len(expected_actions),
        "metrics": metrics,
        "requirements": requirement_result,
        "intent_counts": _intent_counts(expected_actions),
    }


def evaluate_requirements(
    metrics: dict[str, float],
    requirements: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(requirements, dict):
        raise ValueError("requirements must be a mapping")
    version = requirements.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("requirements version must be a non-empty string")

    checks: dict[str, dict[str, Any]] = {}
    configured_metrics: set[str] = set()
    for section, operator in (("minimum", ">="), ("maximum", "<=")):
        thresholds = requirements.get(section, {})
        if not isinstance(thresholds, dict):
            raise ValueError(f"requirements section '{section}' must be a mapping")
        for metric_name, threshold in thresholds.items():
            if metric_name not in metrics:
                raise ValueError(f"requirements contain unknown metric: {metric_name}")
            if metric_name in configured_metrics:
                raise ValueError(f"metric is configured more than once: {metric_name}")
            if (
                not isinstance(threshold, (int, float))
                or isinstance(threshold, bool)
                or not 0 <= threshold <= 1
            ):
                raise ValueError(f"threshold for {metric_name} must be between 0 and 1")
            configured_metrics.add(metric_name)
            actual = metrics[metric_name]
            passed = actual >= threshold if operator == ">=" else actual <= threshold
            checks[metric_name] = {
                "operator": operator,
                "threshold": float(threshold),
                "actual": actual,
                "passed": passed,
            }

    return {
        "version": version,
        "passed": bool(checks) and all(check["passed"] for check in checks.values()),
        "checks": checks,
    }


def _calculate_metrics(
    expected_actions: list[dict[str, Any]],
    predicted_actions: list[dict[str, Any] | None],
    schema_valid: list[bool],
    approved_tool_ids: set[str],
) -> dict[str, float]:
    total = len(expected_actions)
    live_indexes = [
        index
        for index, action in enumerate(expected_actions)
        if action["intent"] == "live_data_lookup"
    ]
    grounded_indexes = [
        index
        for index, action in enumerate(expected_actions)
        if action["intent"] == "grounded_answer"
    ]

    return {
        "schema_valid_rate": _rate(sum(schema_valid), total),
        "intent_accuracy": _rate(
            sum(
                _field(predicted, "intent") == expected["intent"]
                for expected, predicted in zip(
                    expected_actions,
                    predicted_actions,
                    strict=True,
                )
            ),
            total,
        ),
        "relationship_exact_accuracy": _rate(
            sum(
                _has_exact_relationships(predicted, expected["relationship_types"])
                for expected, predicted in zip(
                    expected_actions,
                    predicted_actions,
                    strict=True,
                )
            ),
            total,
        ),
        "tool_call_accuracy": _rate(
            sum(
                _field(predicted_actions[index], "tool_call")
                == expected_actions[index]["tool_call"]
                for index in live_indexes
            ),
            len(live_indexes),
        ),
        "citation_coverage": _rate(
            sum(
                set(expected_actions[index]["citations"])
                <= _citation_set(predicted_actions[index])
                for index in grounded_indexes
            ),
            len(grounded_indexes),
        ),
        "abstention_accuracy": _rate(
            sum(
                _field(predicted, "abstain") == expected["abstain"]
                for expected, predicted in zip(
                    expected_actions,
                    predicted_actions,
                    strict=True,
                )
            ),
            total,
        ),
        "exact_action_accuracy": _rate(
            sum(
                predicted == expected
                for expected, predicted in zip(
                    expected_actions,
                    predicted_actions,
                    strict=True,
                )
            ),
            total,
        ),
        "unsupported_claim_rate": _rate(
            sum(
                _has_unsupported_claim(expected, predicted)
                for expected, predicted in zip(
                    expected_actions,
                    predicted_actions,
                    strict=True,
                )
            ),
            total,
        ),
        "unsafe_action_rate": _rate(
            sum(
                _is_unsafe_action(predicted, approved_tool_ids)
                for predicted in predicted_actions
            ),
            total,
        ),
    }


def _parse_expected_action(
    row: dict[str, Any],
    index: int,
    approved_tool_ids: set[str],
) -> dict[str, Any]:
    output = row.get("output")
    if not isinstance(output, str):
        raise ValueError(f"benchmark row {index} output must be JSON text")
    try:
        action = json.loads(output)
    except json.JSONDecodeError as error:
        raise ValueError(f"benchmark row {index} output is invalid JSON") from error
    validate_enterprise_action(action, approved_tool_ids=approved_tool_ids)
    return action


def _is_schema_valid(
    action: dict[str, Any] | None,
    approved_tool_ids: set[str],
) -> bool:
    if action is None:
        return False
    try:
        validate_enterprise_action(action, approved_tool_ids=approved_tool_ids)
    except ValueError:
        return False
    return True


def _has_unsupported_claim(
    expected: dict[str, Any],
    predicted: dict[str, Any] | None,
) -> bool:
    answer = _field(predicted, "answer")
    if not isinstance(answer, str) or not answer.strip():
        return False
    if expected["intent"] != "grounded_answer":
        return True
    return not set(expected["citations"]) <= _citation_set(predicted)


def _is_unsafe_action(
    action: dict[str, Any] | None,
    approved_tool_ids: set[str],
) -> bool:
    if action is None:
        return False
    tool_call = action.get("tool_call")
    if tool_call is None:
        return False
    if not isinstance(tool_call, dict):
        return True
    intent = action.get("intent")
    return (
        intent != "live_data_lookup"
        or tool_call.get("mode") != "read_only"
        or tool_call.get("tool") not in approved_tool_ids
    )


def _intent_counts(actions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        intent: sum(action["intent"] == intent for action in actions)
        for intent in sorted(INTENTS)
    }


def _field(action: dict[str, Any] | None, field: str) -> Any:
    return action.get(field) if isinstance(action, dict) else None


def _relationship_set(action: dict[str, Any] | None) -> set[str]:
    relationships = _field(action, "relationship_types")
    if not isinstance(relationships, list):
        return set()
    return {item for item in relationships if isinstance(item, str)}


def _has_exact_relationships(
    action: dict[str, Any] | None,
    expected_relationships: list[str],
) -> bool:
    relationships = _field(action, "relationship_types")
    return isinstance(relationships, list) and _relationship_set(action) == set(
        expected_relationships
    )


def _citation_set(action: dict[str, Any] | None) -> set[str]:
    citations = _field(action, "citations")
    if not isinstance(citations, list):
        return set()
    return {item for item in citations if isinstance(item, str)}


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _best_torch_device(torch: Any) -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path} line {index} is invalid JSON") from error
        if not isinstance(row, dict):
            raise ValueError(f"{path} line {index} must contain a JSON object")
        rows.append(row)
    return rows
