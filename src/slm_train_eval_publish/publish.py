from __future__ import annotations

from pathlib import Path

from huggingface_hub import HfApi

from slm_train_eval_publish.config import PipelineConfig


def publish_model(config: PipelineConfig) -> str:
    if config.publish is None:
        raise ValueError("Missing publish config. Add a 'publish' section to the YAML file.")

    model_dir = Path(config.publish.model_dir)
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    api = HfApi()
    api.create_repo(
        repo_id=config.publish.repo_id,
        private=config.publish.private,
        exist_ok=True,
    )
    api.upload_folder(
        repo_id=config.publish.repo_id,
        folder_path=str(model_dir),
        commit_message=config.publish.commit_message,
    )
    return f"https://huggingface.co/{config.publish.repo_id}"
