from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slm_train_eval_publish.airo_actions import evaluate_airo_actions_predictions


def airo_action_prompt(row: dict[str, Any]) -> str:
    instruction = str(row.get("instruction", "")).strip()
    input_text = str(row.get("input", "")).strip()
    if not instruction:
        raise ValueError("Instruction field is required for prediction prompt")
    if input_text:
        return (
            "### Instruction\n"
            f"{instruction}\n\n"
            "### Input\n"
            f"{input_text}\n\n"
            "### Response\n"
        )
    return (
        "### Instruction\n"
        f"{instruction}\n\n"
        "### Response\n"
    )


def predict_airo_actions_with_model(
    dataset: Path,
    model_path: Path,
    output: Path,
    *,
    limit: int | None = None,
    max_new_tokens: int = 128,
) -> Path:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    rows = _read_jsonl(dataset)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise ValueError("Dataset has no rows to predict")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if (model_path / "adapter_config.json").exists():
        from peft import AutoPeftModelForCausalLM

        model = AutoPeftModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
        )

    device = _best_torch_device(torch)
    model.to(device)
    model.eval()

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for i, row in enumerate(rows):
            prompt = airo_action_prompt(row)
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            decoded = tokenizer.decode(output_ids[0], skip_special_tokens=True)
            completion = decoded[len(prompt) :].strip()

            record = {
                "instruction": row.get("instruction", ""),
                "input": row.get("input", ""),
                "output": row.get("output", ""),
                "expected": row.get("output", ""),
                "prediction": completion,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return output


def evaluate_airo_actions_model(
    dataset: Path,
    model_path: Path,
    output_report: Path,
    *,
    predictions_output: Path | None = None,
    limit: int | None = None,
    max_new_tokens: int = 128,
    reuse_predictions: bool = True,
) -> dict[str, Any]:
    if predictions_output is None:
        predictions_output = output_report.parent / "eval_predictions.jsonl"

    dataset_rows = _read_jsonl(dataset)
    expected_count = limit if limit is not None else len(dataset_rows)

    should_predict = True
    if reuse_predictions and predictions_output.exists():
        existing_rows = _read_jsonl(predictions_output)
        if len(existing_rows) == expected_count:
            should_predict = False

    if should_predict:
        predict_airo_actions_with_model(
            dataset=dataset,
            model_path=model_path,
            output=predictions_output,
            limit=limit,
            max_new_tokens=max_new_tokens,
        )

    pred_rows = _read_jsonl(predictions_output)
    predictions = [r["prediction"] for r in pred_rows]
    report = evaluate_airo_actions_predictions(pred_rows, predictions)

    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _best_torch_device(torch: Any) -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
