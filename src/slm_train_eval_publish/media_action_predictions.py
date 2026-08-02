from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from slm_train_eval_publish.structured_output import extract_first_json_object

INVALID_MEDIA_ACTION = {
    "intent": "invalid",
    "tool": "media.invalid",
    "confidence": 0.0,
    "constraints": {},
    "missing_fields": [],
    "clarification_required": True,
}


def predict_media_actions_with_model(
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
        raise ValueError("dataset has no rows to predict")

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if (model_path / "adapter_config.json").exists():
        from peft import AutoPeftModelForCausalLM

        model = AutoPeftModelForCausalLM.from_pretrained(model_path, torch_dtype="auto")
    else:
        model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype="auto")

    device = _best_torch_device(torch)
    model.to(device)
    model.eval()

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            prompt = media_action_prompt(row)
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            decoded = tokenizer.decode(output_ids[0], skip_special_tokens=True)
            completion = decoded[len(prompt) :].strip()
            payload, error = parse_media_action_completion(completion)
            handle.write(
                json.dumps(
                    {
                        "input": row["input"],
                        "output": payload,
                        "raw_completion": completion,
                        "parse_error": error,
                    },
                    ensure_ascii=False,
                )
            )
            handle.write("\n")

    return output


def media_action_prompt(row: dict[str, Any]) -> str:
    instruction = str(row.get("instruction", "")).strip()
    input_text = str(row.get("input", "")).strip()
    if not instruction or not input_text:
        raise ValueError("media action rows require instruction and input fields")
    return (
        "### Instruction\n"
        f"{instruction}\n\n"
        "### Input\n"
        f"{input_text}\n\n"
        "### Response\n"
    )


def parse_media_action_completion(completion: str) -> tuple[dict[str, Any], str | None]:
    json_text = extract_first_json_object(completion)
    if json_text is None:
        return dict(INVALID_MEDIA_ACTION), "no JSON object found"
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as error:
        return dict(INVALID_MEDIA_ACTION), f"invalid JSON: {error.msg}"
    if not isinstance(parsed, dict):
        return dict(INVALID_MEDIA_ACTION), "JSON payload is not an object"
    error = validate_media_action_payload(parsed)
    if error is not None:
        return dict(INVALID_MEDIA_ACTION), error
    return parsed, None


def validate_media_action_payload(payload: dict[str, Any]) -> str | None:
    required: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "intent": str,
        "tool": str,
        "confidence": (int, float),
        "constraints": dict,
        "missing_fields": list,
        "clarification_required": bool,
    }
    for field, expected_type in required.items():
        value = payload.get(field)
        if not isinstance(value, expected_type):
            return f"missing or invalid {field}"
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _best_torch_device(torch: Any) -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
