from __future__ import annotations

from pathlib import Path

import pytest

from slm_train_eval_publish.config import load_config


def test_load_starter_config() -> None:
    config = load_config(Path("configs/sft.yaml"))

    assert config.model.base_model == "HuggingFaceTB/SmolLM2-135M-Instruct"
    assert config.data.train_path == "examples/sample_sft.jsonl"
    assert config.lora.enabled is True
    assert config.training.backend == "transformers"
    assert config.training.fp16 is False
    assert config.training.bf16 is False
    assert config.publish is not None


def test_load_airo_media_actions_smoke_config() -> None:
    config = load_config(Path("configs/airo_media_actions_smoke_sft.yaml"))

    assert config.data.train_path == "data/processed/airo_media_actions_smoke_train.jsonl"
    assert config.training.output_dir == "models/airo-media-actions-smollm2-135m-smoke"
    assert config.eval.max_eval_samples == 8


def test_load_enterprise_knowledge_config() -> None:
    config = load_config(Path("configs/enterprise_knowledge_sft.yaml"))

    assert config.data.train_path == "data/processed/enterprise_knowledge_train.jsonl"
    assert config.data.eval_path == "data/processed/enterprise_knowledge_eval.jsonl"
    assert config.data.validation_profile == "enterprise_knowledge_v1"
    assert (
        config.data.validation_context_path
        == "examples/enterprise_knowledge/metadata_catalog.json"
    )
    assert config.training.output_dir == "models/enterprise-knowledge-smollm2-360m"


def test_load_enterprise_knowledge_smoke_config() -> None:
    config = load_config(Path("configs/enterprise_knowledge_smoke_sft.yaml"))

    assert config.data.train_path == "data/processed/enterprise_knowledge_smoke_train.jsonl"
    assert config.data.validation_profile == "enterprise_knowledge_v1"
    assert config.training.num_train_epochs == 1
    assert config.training.output_dir == "models/enterprise-knowledge-smollm2-360m-smoke"


def test_load_enterprise_knowledge_schema_config() -> None:
    config = load_config(Path("configs/enterprise_knowledge_schema_sft.yaml"))

    assert config.data.train_path == "data/processed/enterprise_knowledge_schema_train.jsonl"
    assert config.training.num_train_epochs == 4
    assert config.lora.target_modules == [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ]
    assert (
        config.training.output_dir
        == "models/enterprise-knowledge-smollm2-360m-schema-v2"
    )


def test_load_enterprise_knowledge_context_config() -> None:
    config = load_config(Path("configs/enterprise_knowledge_context_sft.yaml"))

    assert config.data.train_path == "data/processed/enterprise_knowledge_context_train.jsonl"
    assert config.training.num_train_epochs == 2
    assert config.training.use_cpu is False
    assert config.lora.target_modules == ["q_proj", "v_proj"]
    assert (
        config.training.output_dir
        == "models/enterprise-knowledge-smollm2-360m-context-v3"
    )


def test_load_enterprise_knowledge_context_mlx_config() -> None:
    config = load_config(Path("configs/enterprise_knowledge_context_mlx_sft.yaml"))

    assert config.training.backend == "mlx"
    assert config.training.mlx_num_layers == -1
    assert config.lora.target_modules == ["q_proj", "v_proj"]


def test_load_config_supports_explicit_cpu_training(tmp_path: Path) -> None:
    config_path = tmp_path / "cpu.yaml"
    config_path.write_text(
        """
model:
  base_model: test/model
data:
  train_path: train.jsonl
training:
  use_cpu: true
""".strip()
    )

    assert load_config(config_path).training.use_cpu is True


def test_rejects_unknown_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
model:
  base_model: test/model
  typo: true
data:
  train_path: examples/sample_sft.jsonl
""".strip()
    )

    with pytest.raises(ValueError, match="Unknown key"):
        load_config(config_path)


def test_rejects_unknown_training_backend(tmp_path: Path) -> None:
    config_path = tmp_path / "bad-backend.yaml"
    config_path.write_text(
        """
model:
  base_model: test/model
data:
  train_path: train.jsonl
training:
  backend: mystery-cloud
""".strip()
    )

    with pytest.raises(ValueError, match="training.backend"):
        load_config(config_path)


def test_rejects_invalid_mlx_layer_count(tmp_path: Path) -> None:
    config_path = tmp_path / "bad-mlx.yaml"
    config_path.write_text(
        """
model:
  base_model: test/model
data:
  train_path: train.jsonl
training:
  backend: mlx
  mlx_num_layers: 0
""".strip()
    )

    with pytest.raises(ValueError, match="mlx_num_layers"):
        load_config(config_path)


@pytest.mark.parametrize(
    "path,model,rank",
    [
        (
            "configs/enterprise_knowledge_cloud_smollm2_1_7b.yaml",
            "HuggingFaceTB/SmolLM2-1.7B-Instruct",
            16,
        ),
        (
            "configs/enterprise_knowledge_cloud_qwen2_5_1_5b.yaml",
            "Qwen/Qwen2.5-1.5B-Instruct",
            16,
        ),
        (
            "configs/enterprise_knowledge_cloud_qwen2_5_1_5b_rank32.yaml",
            "Qwen/Qwen2.5-1.5B-Instruct",
            32,
        ),
    ],
)
def test_loads_cloud_quality_sweep_configs(path: str, model: str, rank: int) -> None:
    config = load_config(Path(path))

    assert config.model.base_model == model
    assert config.data.train_path == "data/processed/enterprise_knowledge_cloud_train.jsonl"
    assert config.training.backend == "transformers"
    assert config.training.fp16 is True
    assert config.training.bf16 is False
    assert config.lora.r == rank


def test_rejects_conflicting_mixed_precision(tmp_path: Path) -> None:
    config_path = tmp_path / "bad-precision.yaml"
    config_path.write_text(
        """
model:
  base_model: test/model
data:
  train_path: train.jsonl
training:
  fp16: true
  bf16: true
""".strip()
    )

    with pytest.raises(ValueError, match="fp16 and bf16"):
        load_config(config_path)
