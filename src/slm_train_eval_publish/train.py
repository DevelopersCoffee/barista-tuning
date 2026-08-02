from __future__ import annotations

from pathlib import Path
from typing import Any

from slm_train_eval_publish.config import PipelineConfig
from slm_train_eval_publish.data import format_sft_prompt_and_output, load_sft_datasets


def train_model(config: PipelineConfig) -> Path:
    if config.training.backend == "mlx":
        from slm_train_eval_publish.mlx_training import train_model_with_mlx

        return train_model_with_mlx(config)
    return train_model_with_transformers(config)


def train_model_with_transformers(config: PipelineConfig) -> Path:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(config.training.seed)

    tokenizer = AutoTokenizer.from_pretrained(
        config.model.base_model,
        trust_remote_code=config.model.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {
        "torch_dtype": config.model.torch_dtype,
        "trust_remote_code": config.model.trust_remote_code,
    }
    if config.model.use_flash_attention_2:
        model_kwargs["attn_implementation"] = "flash_attention_2"

    model = AutoModelForCausalLM.from_pretrained(config.model.base_model, **model_kwargs)
    model.config.use_cache = False
    _enable_input_grads_for_checkpointing(model, config)

    if config.lora.enabled:
        from peft import LoraConfig, get_peft_model

        peft_config = LoraConfig(
            r=config.lora.r,
            lora_alpha=config.lora.alpha,
            lora_dropout=config.lora.dropout,
            target_modules=config.lora.target_modules,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)

    train_dataset, eval_dataset = load_sft_datasets(config.data)
    train_dataset = _tokenize_dataset(train_dataset, tokenizer, config)
    if eval_dataset is not None:
        eval_dataset = _tokenize_dataset(eval_dataset, tokenizer, config)

    args = TrainingArguments(
        output_dir=config.training.output_dir,
        seed=config.training.seed,
        num_train_epochs=config.training.num_train_epochs,
        per_device_train_batch_size=config.training.per_device_train_batch_size,
        per_device_eval_batch_size=config.training.per_device_eval_batch_size,
        gradient_accumulation_steps=config.training.gradient_accumulation_steps,
        learning_rate=config.training.learning_rate,
        warmup_ratio=config.training.warmup_ratio,
        weight_decay=config.training.weight_decay,
        logging_steps=config.training.logging_steps,
        save_steps=config.training.save_steps,
        eval_steps=config.training.eval_steps,
        save_total_limit=config.training.save_total_limit,
        gradient_checkpointing=config.training.gradient_checkpointing,
        use_cpu=config.training.use_cpu,
        report_to=config.training.report_to,
        eval_strategy="steps" if eval_dataset is not None else "no",
        save_strategy="steps",
        bf16=config.training.bf16,
        fp16=config.training.fp16,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=ResponseOnlyDataCollator(tokenizer),
    )
    trainer.train()
    trainer.save_model(config.training.output_dir)
    tokenizer.save_pretrained(config.training.output_dir)

    return Path(config.training.output_dir)


def _tokenize_dataset(dataset: Any, tokenizer: Any, config: PipelineConfig) -> Any:
    def tokenize(example: dict[str, Any]) -> dict[str, Any]:
        prompt, output = format_sft_prompt_and_output(example, config.data)
        text = f"{prompt}{output}"
        if tokenizer.eos_token and not output.endswith(tokenizer.eos_token):
            text = f"{text}{tokenizer.eos_token}"

        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=config.data.max_seq_length,
            padding=False,
        )
        prompt_ids = tokenizer(
            prompt,
            truncation=True,
            max_length=config.data.max_seq_length,
            padding=False,
        )["input_ids"]
        labels = list(tokenized["input_ids"])
        prompt_token_count = min(len(prompt_ids), len(labels))
        labels[:prompt_token_count] = [-100] * prompt_token_count
        tokenized["labels"] = labels
        return tokenized

    remove_columns = list(getattr(dataset, "column_names", []))
    return dataset.map(tokenize, remove_columns=remove_columns)


class ResponseOnlyDataCollator:
    def __init__(self, tokenizer: Any) -> None:
        self.tokenizer = tokenizer

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        import torch

        pad_token_id = self.tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = self.tokenizer.eos_token_id
        if pad_token_id is None:
            pad_token_id = 0

        max_length = max(len(feature["input_ids"]) for feature in features)
        input_ids = []
        attention_mask = []
        labels = []
        for feature in features:
            pad_length = max_length - len(feature["input_ids"])
            input_ids.append(feature["input_ids"] + [pad_token_id] * pad_length)
            attention_mask.append(feature["attention_mask"] + [0] * pad_length)
            labels.append(feature["labels"] + [-100] * pad_length)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def _enable_input_grads_for_checkpointing(model: Any, config: PipelineConfig) -> None:
    if config.training.gradient_checkpointing and hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
