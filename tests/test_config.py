from __future__ import annotations

from pathlib import Path

import pytest

from slm_train_eval_publish.config import load_config


def test_load_starter_config() -> None:
    config = load_config(Path("configs/sft.yaml"))

    assert config.model.base_model == "HuggingFaceTB/SmolLM2-135M-Instruct"
    assert config.data.train_path == "examples/sample_sft.jsonl"
    assert config.lora.enabled is True
    assert config.publish is not None


def test_load_airo_media_actions_smoke_config() -> None:
    config = load_config(Path("configs/airo_media_actions_smoke_sft.yaml"))

    assert config.data.train_path == "data/processed/airo_media_actions_smoke_train.jsonl"
    assert config.training.output_dir == "models/airo-media-actions-smollm2-135m-smoke"
    assert config.eval.max_eval_samples == 8


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
