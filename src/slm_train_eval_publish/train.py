from __future__ import annotations

from pathlib import Path
from typing import Any

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    set_seed,
)

from slm_train_eval_publish.config import PipelineConfig
from slm_train_eval_publish.data import format_sft_example, load_sft_datasets


def train_model(config: PipelineConfig) -> Path:
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
        report_to=config.training.report_to,
        eval_strategy="steps" if eval_dataset is not None else "no",
        save_strategy="steps",
        bf16=False,
        fp16=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    trainer.save_model(config.training.output_dir)
    tokenizer.save_pretrained(config.training.output_dir)

    return Path(config.training.output_dir)


def _tokenize_dataset(dataset: Any, tokenizer: Any, config: PipelineConfig) -> Any:
    def tokenize(example: dict[str, Any]) -> dict[str, Any]:
        text = format_sft_example(example, config.data)
        if tokenizer.eos_token and not text.endswith(tokenizer.eos_token):
            text = f"{text}{tokenizer.eos_token}"
        return tokenizer(
            text,
            truncation=True,
            max_length=config.data.max_seq_length,
            padding=False,
        )

    remove_columns = list(getattr(dataset, "column_names", []))
    return dataset.map(tokenize, remove_columns=remove_columns)
