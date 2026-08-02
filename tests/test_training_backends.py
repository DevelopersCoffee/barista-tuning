from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import pytest
import yaml

from slm_train_eval_publish.config import load_config
from slm_train_eval_publish.mlx_training import (
    build_mlx_lora_config,
    prepare_mlx_dataset,
    require_apple_silicon,
)
from slm_train_eval_publish.training_job import package_training_job


def _write_config(tmp_path: Path, *, backend: str = "mlx") -> Path:
    train_path = tmp_path / "source" / "train.jsonl"
    eval_path = tmp_path / "source" / "eval.jsonl"
    context_path = tmp_path / "source" / "catalog.json"
    train_path.parent.mkdir()
    rows = [
        {"instruction": "Classify safely", "input": f"request {index}", "output": "{}"}
        for index in range(5)
    ]
    train_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    eval_path.write_text(json.dumps(rows[0]) + "\n")
    context_path.write_text('{"version": "1"}\n')
    config_path = tmp_path / "job.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {"base_model": "test/model"},
                "data": {
                    "train_path": str(train_path),
                    "eval_path": str(eval_path),
                    "validation_context_path": str(context_path),
                    "max_seq_length": 512,
                },
                "lora": {
                    "r": 8,
                    "alpha": 16,
                    "dropout": 0.1,
                    "target_modules": ["q_proj", "v_proj"],
                },
                "training": {
                    "backend": backend,
                    "output_dir": str(tmp_path / "adapter"),
                    "num_train_epochs": 2,
                    "per_device_train_batch_size": 2,
                    "gradient_accumulation_steps": 2,
                    "learning_rate": 0.0002,
                    "logging_steps": 3,
                    "eval_steps": 4,
                    "save_steps": 5,
                    "mlx_num_layers": -1,
                },
            },
            sort_keys=False,
        )
    )
    return config_path


def test_prepare_mlx_dataset_preserves_prompt_completion_contract(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))

    data_dir, train_rows = prepare_mlx_dataset(config)

    row = json.loads((data_dir / "train.jsonl").read_text().splitlines()[0])
    assert train_rows == 5
    assert row == {
        "prompt": "### Instruction\nClassify safely\n\n### Input\nrequest 0\n\n### Response\n",
        "completion": "{}",
    }
    assert (data_dir / "valid.jsonl").exists()


def test_build_mlx_config_maps_training_semantics(tmp_path: Path) -> None:
    config = load_config(_write_config(tmp_path))

    mlx_config = build_mlx_lora_config(config, tmp_path / "mlx-data", train_rows=5)

    assert mlx_config["model"] == "test/model"
    assert mlx_config["train"] is True
    assert mlx_config["iters"] == 6
    assert mlx_config["batch_size"] == 2
    assert mlx_config["grad_accumulation_steps"] == 2
    assert mlx_config["steps_per_report"] == 6
    assert mlx_config["steps_per_eval"] == 8
    assert mlx_config["save_every"] == 10
    assert mlx_config["lr_schedule"] == {
        "name": "cosine_decay",
        "arguments": [0.0002, 3],
        "warmup": 1,
        "warmup_init": 0.0,
    }
    assert mlx_config["mask_prompt"] is True
    assert mlx_config["lora_parameters"] == {
        "rank": 8,
        "scale": 2.0,
        "dropout": 0.1,
        "keys": ["self_attn.q_proj", "self_attn.v_proj"],
    }


def test_require_apple_silicon_rejects_other_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")

    with pytest.raises(RuntimeError, match="Apple Silicon"):
        require_apple_silicon()


def test_package_training_job_is_relocatable_and_checksummed(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, backend="transformers")

    bundle = package_training_job(config_path, tmp_path / "bundle")

    bundled_config = yaml.safe_load((bundle / "config.yaml").read_text())
    manifest = json.loads((bundle / "job.json").read_text())
    assert bundled_config["data"]["train_path"] == "data/train.jsonl"
    assert bundled_config["data"]["eval_path"] == "data/eval.jsonl"
    assert bundled_config["data"]["validation_context_path"] == "data/context.json"
    assert bundled_config["training"]["output_dir"] == "output/model"
    assert manifest["backend"] == "transformers"
    assert manifest["install_extra"] == "train"
    assert manifest["command"] == ["slm", "train", "config.yaml"]
    assert {item["path"] for item in manifest["inputs"]} == {
        "config.yaml",
        "data/context.json",
        "data/eval.jsonl",
        "data/train.jsonl",
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["inputs"])


def test_package_training_job_does_not_overwrite_existing_directory(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    output = tmp_path / "bundle"
    output.mkdir()
    (output / "keep.txt").write_text("keep")

    with pytest.raises(FileExistsError, match="not empty"):
        package_training_job(config_path, output)
