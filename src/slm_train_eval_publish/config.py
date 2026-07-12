from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModelConfig:
    base_model: str
    torch_dtype: str = "auto"
    trust_remote_code: bool = False
    use_flash_attention_2: bool = False


@dataclass(frozen=True)
class DataConfig:
    train_path: str
    eval_path: str | None = None
    dataset_name: str | None = None
    dataset_config: str | None = None
    train_split: str = "train"
    eval_split: str = "validation"
    instruction_field: str = "instruction"
    input_field: str = "input"
    output_field: str = "output"
    text_field: str | None = None
    max_seq_length: int = 2048


@dataclass(frozen=True)
class LoraConfig:
    enabled: bool = True
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])


@dataclass(frozen=True)
class TrainingConfig:
    output_dir: str = "models/sft"
    seed: int = 42
    num_train_epochs: float = 1.0
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    logging_steps: int = 10
    save_steps: int = 200
    eval_steps: int = 200
    save_total_limit: int = 2
    gradient_checkpointing: bool = True
    report_to: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalConfig:
    model_path: str = "models/sft"
    output_dir: str = "reports"
    max_eval_samples: int = 128
    generation_prompts: list[str] = field(default_factory=list)
    max_new_tokens: int = 128


@dataclass(frozen=True)
class PublishConfig:
    repo_id: str
    model_dir: str = "models/sft"
    private: bool = True
    commit_message: str = "Publish SLM artifact"


@dataclass(frozen=True)
class PipelineConfig:
    model: ModelConfig
    data: DataConfig
    training: TrainingConfig = field(default_factory=TrainingConfig)
    lora: LoraConfig = field(default_factory=LoraConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    publish: PublishConfig | None = None


def load_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping at top level in {config_path}")

    return PipelineConfig(
        model=_build(ModelConfig, raw.get("model", {}), "model"),
        data=_build(DataConfig, raw.get("data", {}), "data"),
        training=_build(TrainingConfig, raw.get("training", {}), "training"),
        lora=_build(LoraConfig, raw.get("lora", {}), "lora"),
        eval=_build(EvalConfig, raw.get("eval", {}), "eval"),
        publish=_build(PublishConfig, raw["publish"], "publish") if raw.get("publish") else None,
    )


def _build(cls: type[Any], values: dict[str, Any], section: str) -> Any:
    if not isinstance(values, dict):
        raise ValueError(f"Config section '{section}' must be a mapping")

    valid = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
    unknown = sorted(set(values) - valid)
    if unknown:
        raise ValueError(f"Unknown key(s) in '{section}': {', '.join(unknown)}")

    try:
        return cls(**values)
    except TypeError as exc:
        raise ValueError(f"Invalid config section '{section}': {exc}") from exc
