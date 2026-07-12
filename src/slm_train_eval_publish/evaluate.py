from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from slm_train_eval_publish.config import PipelineConfig
from slm_train_eval_publish.data import format_sft_example, load_sft_datasets


def evaluate_model(config: PipelineConfig) -> Path:
    output_dir = Path(config.eval.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        config.eval.model_path,
        trust_remote_code=config.model.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if (Path(config.eval.model_path) / "adapter_config.json").exists():
        from peft import AutoPeftModelForCausalLM

        model = AutoPeftModelForCausalLM.from_pretrained(
            config.eval.model_path,
            torch_dtype=config.model.torch_dtype,
            trust_remote_code=config.model.trust_remote_code,
            device_map="auto",
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            config.eval.model_path,
            torch_dtype=config.model.torch_dtype,
            trust_remote_code=config.model.trust_remote_code,
            device_map="auto",
        )
    model.eval()

    _, eval_dataset = load_sft_datasets(config.data)
    if eval_dataset is None:
        eval_dataset, _ = load_sft_datasets(config.data)

    metrics = _perplexity(model, tokenizer, eval_dataset, config)
    generations = _generate_samples(model, tokenizer, config)

    report = {
        "model_path": config.eval.model_path,
        "metrics": metrics,
        "generations": generations,
    }
    report_path = output_dir / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report_path


def _perplexity(
    model: Any,
    tokenizer: Any,
    dataset: Any,
    config: PipelineConfig,
) -> dict[str, float]:
    losses: list[float] = []
    max_samples = min(len(dataset), config.eval.max_eval_samples)

    for index in range(max_samples):
        text = format_sft_example(dataset[index], config.data)
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=config.data.max_seq_length,
        )
        inputs = {key: value.to(model.device) for key, value in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs, labels=inputs["input_ids"])
        losses.append(float(outputs.loss.detach().cpu()))

    mean_loss = sum(losses) / len(losses) if losses else float("nan")
    return {
        "eval_samples": float(max_samples),
        "loss": mean_loss,
        "perplexity": math.exp(mean_loss) if losses and mean_loss < 20 else float("inf"),
    }


def _generate_samples(model: Any, tokenizer: Any, config: PipelineConfig) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    for prompt in config.eval.generation_prompts:
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=config.eval.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        samples.append({"prompt": prompt, "completion": text[len(prompt) :].strip()})
    return samples
