from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from litert_torch.generative.export_hf import export as litert_export


def merge_peft_adapter(
    adapter_path: Path,
    merged_output_dir: Path,
) -> Path:
    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    print(f"Loading adapter from {adapter_path}...")
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    model = AutoPeftModelForCausalLM.from_pretrained(
        adapter_path,
        torch_dtype=torch.float32,
    )

    print("Merging LoRA weights into base model...")
    merged_model = model.merge_and_unload()

    merged_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving merged model to {merged_output_dir}...")
    merged_model.save_pretrained(merged_output_dir)
    tokenizer.save_pretrained(merged_output_dir)
    return merged_output_dir


def export_airo_actions_litertlm(
    model_path: Path,
    output_dir: Path,
    *,
    artifact_name: str = "airo_actions_q8_ekv1024.litertlm",
    schema_source: Path | None = None,
    prefill_lengths: list[int] | None = None,
    cache_length: int = 1024,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if prefill_lengths is None:
        prefill_lengths = [64, 128]

    # Check if adapter needs merging
    if (model_path / "adapter_config.json").exists():
        merged_dir = output_dir / "merged_checkpoint"
        source_model_dir = merge_peft_adapter(model_path, merged_dir)
    else:
        source_model_dir = model_path

    export_tmp_dir = output_dir / "litert_build"
    export_tmp_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting to LiteRT-LM format from {source_model_dir}...")
    litert_export.export(
        model=str(source_model_dir),
        output_dir=str(export_tmp_dir),
        task="text_generation",
        prefill_lengths=prefill_lengths,
        cache_length=cache_length,
        quantization_recipe="dynamic_wi8_afp32",
        bundle_litert_lm=True,
    )

    # Locate generated .litertlm file
    generated_litertlm = None
    for cand in export_tmp_dir.glob("*.litertlm"):
        generated_litertlm = cand
        break

    if not generated_litertlm or not generated_litertlm.exists():
        raise FileNotFoundError(f"Export did not produce a .litertlm file in {export_tmp_dir}")

    target_litertlm = output_dir / artifact_name
    shutil.copy2(generated_litertlm, target_litertlm)

    # Copy / write tools schema
    schema_target = output_dir / "tools_schema.json"
    if schema_source and schema_source.exists():
        shutil.copy2(schema_source, schema_target)
    else:
        default_schema = Path("schemas/airo-actions/v1/tools_schema.json")
        if default_schema.exists():
            shutil.copy2(default_schema, schema_target)

    # Compute metrics
    file_bytes = target_litertlm.stat().st_size
    sha256 = hashlib.sha256(target_litertlm.read_bytes()).hexdigest()

    manifest = {
        "artifact_name": artifact_name,
        "artifact_path": str(target_litertlm.resolve()),
        "file_size_bytes": file_bytes,
        "sha256": sha256,
        "schema_path": str(schema_target.resolve()),
        "prefill_lengths": prefill_lengths,
        "context_length": cache_length,
        "quantization": "dynamic_int8 (dynamic_wi8_afp32)",
        "parameter_count": 268098176,
    }

    manifest_path = output_dir / "export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"LiteRT-LM export complete: {target_litertlm}")
    print(f"Size: {file_bytes} bytes")
    print(f"SHA-256: {sha256}")
    return manifest
