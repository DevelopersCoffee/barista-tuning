from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from slm_train_eval_publish.config import load_config

app = typer.Typer(help="Train, evaluate, and publish small language models.")
console = Console()


@app.command()
def train(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Fine-tune the configured base model."""
    from slm_train_eval_publish.train import train_model

    output_dir = train_model(load_config(config))
    console.print(f"Training complete: {output_dir}")


@app.command()
def evaluate(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Evaluate the configured model artifact."""
    from slm_train_eval_publish.evaluate import evaluate_model

    report_path = evaluate_model(load_config(config))
    console.print(f"Evaluation report written: {report_path}")


@app.command()
def publish(config: Annotated[Path, typer.Argument(exists=True, readable=True)]) -> None:
    """Publish the configured model artifact to Hugging Face Hub."""
    from slm_train_eval_publish.publish import publish_model

    url = publish_model(load_config(config))
    console.print(f"Published model: {url}")


if __name__ == "__main__":
    app()
