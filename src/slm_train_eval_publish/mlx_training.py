from __future__ import annotations

import json
import math
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from slm_train_eval_publish.config import PipelineConfig
from slm_train_eval_publish.data import format_sft_prompt_and_output
from slm_train_eval_publish.dataset_validation import validate_sft_rows

_MLX_TARGET_KEYS = {
    "q_proj": "self_attn.q_proj",
    "k_proj": "self_attn.k_proj",
    "v_proj": "self_attn.v_proj",
    "o_proj": "self_attn.o_proj",
    "gate_proj": "mlp.gate_proj",
    "up_proj": "mlp.up_proj",
    "down_proj": "mlp.down_proj",
}


def require_apple_silicon() -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise RuntimeError("The MLX training backend requires macOS on Apple Silicon")


def prepare_mlx_dataset(config: PipelineConfig) -> tuple[Path, int]:
    if config.data.dataset_name:
        raise ValueError("The MLX backend currently requires local JSON or JSONL inputs")

    output_dir = Path(config.training.output_dir).resolve()
    data_dir = output_dir / ".mlx-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    train_rows = _read_jsonl(Path(config.data.train_path))
    validate_sft_rows(
        train_rows,
        config.data.validation_profile,
        validation_context_path=config.data.validation_context_path,
    )
    _write_completion_rows(train_rows, data_dir / "train.jsonl", config)

    if config.data.eval_path:
        eval_rows = _read_jsonl(Path(config.data.eval_path))
        validate_sft_rows(
            eval_rows,
            config.data.validation_profile,
            validation_context_path=config.data.validation_context_path,
        )
        _write_completion_rows(eval_rows, data_dir / "valid.jsonl", config)

    return data_dir, len(train_rows)


def build_mlx_lora_config(
    config: PipelineConfig,
    data_dir: Path,
    *,
    train_rows: int,
) -> dict[str, Any]:
    batch_size = config.training.per_device_train_batch_size
    iterations_per_epoch = math.ceil(train_rows / batch_size)
    iterations = max(1, math.ceil(iterations_per_epoch * config.training.num_train_epochs))
    accumulation = config.training.gradient_accumulation_steps
    optimizer_steps = math.ceil(iterations / accumulation)
    lora_parameters: dict[str, Any] | None = None
    if config.lora.enabled:
        unknown_targets = sorted(set(config.lora.target_modules) - set(_MLX_TARGET_KEYS))
        if unknown_targets:
            raise ValueError(
                "Unsupported MLX LoRA target module(s): " + ", ".join(unknown_targets)
            )
        lora_parameters = {
            "rank": config.lora.r,
            "scale": config.lora.alpha / config.lora.r,
            "dropout": config.lora.dropout,
            "keys": [_MLX_TARGET_KEYS[name] for name in config.lora.target_modules],
        }

    mlx_config: dict[str, Any] = {
        "model": config.model.base_model,
        "train": True,
        "fine_tune_type": "lora" if config.lora.enabled else "full",
        "data": str(data_dir.resolve()),
        "seed": config.training.seed,
        "num_layers": config.training.mlx_num_layers,
        "batch_size": batch_size,
        "iters": iterations,
        "val_batches": -1,
        "learning_rate": config.training.learning_rate,
        "steps_per_report": config.training.logging_steps * accumulation,
        "steps_per_eval": config.training.eval_steps * accumulation,
        "grad_accumulation_steps": accumulation,
        "adapter_path": str(Path(config.training.output_dir).resolve()),
        "save_every": config.training.save_steps * accumulation,
        "max_seq_length": config.data.max_seq_length,
        "grad_checkpoint": config.training.gradient_checkpointing,
        "mask_prompt": True,
        "trust_remote_code": config.model.trust_remote_code,
    }
    if lora_parameters is not None:
        mlx_config["lora_parameters"] = lora_parameters
    if config.training.weight_decay:
        mlx_config["optimizer"] = "adamw"
        mlx_config["optimizer_config"] = {
            "adamw": {"weight_decay": config.training.weight_decay}
        }
    if config.training.warmup_ratio:
        mlx_config["lr_schedule"] = {
            "name": "cosine_decay",
            "arguments": [config.training.learning_rate, optimizer_steps],
            "warmup": math.ceil(optimizer_steps * config.training.warmup_ratio),
            "warmup_init": 0.0,
        }
    if config.training.report_to:
        mlx_config["report_to"] = ",".join(config.training.report_to)
    return mlx_config


def train_model_with_mlx(config: PipelineConfig) -> Path:
    require_apple_silicon()
    data_dir, train_rows = prepare_mlx_dataset(config)
    output_dir = Path(config.training.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    mlx_config_path = output_dir / "mlx_lora_config.yaml"
    mlx_config_path.write_text(
        yaml.safe_dump(
            build_mlx_lora_config(config, data_dir, train_rows=train_rows),
            sort_keys=False,
        )
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "mlx_lm", "lora", "--config", str(mlx_config_path)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"MLX training failed with exit code {exc.returncode}") from exc
    return output_dir


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() not in {".json", ".jsonl"}:
        raise ValueError("The MLX backend supports local JSONL inputs")
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        rows.append(row)
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def _write_completion_rows(
    rows: list[dict[str, Any]],
    path: Path,
    config: PipelineConfig,
) -> None:
    with path.open("w") as handle:
        for row in rows:
            prompt, completion = format_sft_prompt_and_output(row, config.data)
            handle.write(json.dumps({"prompt": prompt, "completion": completion}) + "\n")
