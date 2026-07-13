---
license: apache-2.0
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
library_name: peft
tags:
  - airo-tv
  - edge-intelligence
  - llama-cpp
  - media-actions
  - function-calling
---

# Airo Media Actions SmolLM2 135M

Task-specific local intent model for Airo TV edge intelligence. It translates
natural-language media requests into deterministic media-action JSON consumed by
the `slm_edge_intelligence` Rust/Flutter runtime.

Base model: `HuggingFaceTB/SmolLM2-135M-Instruct`

## Files

- `peft-adapter/` - PEFT LoRA adapter and tokenizer files.
- `gguf/airo-media-actions-lora-f16.gguf` - llama.cpp LoRA adapter for use with
  a compatible SmolLM2 135M Instruct GGUF base model.
- `gguf/airo-media-actions-smollm2-135m-merged-f16.gguf` - standalone merged F16
  GGUF for easiest edge deployment.
- `reports/airo_media_actions_rule_vs_slm.json` - strict eval summary.
- `reports/airo_media_actions_slm_predictions.jsonl` - generated eval
  predictions.

## Expected Output

Prompt:

```text
### Instruction
Translate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.

### Input
Show Hindi news

### Response
```

Output:

```json
{"clarification_required":false,"confidence":0.91,"constraints":{"genre":"news","language":"hi","live":true},"intent":"search","missing_fields":[],"tool":"media.search"}
```

## llama.cpp

Use `llama-completion` for raw completion mode:

```bash
llama-completion \
  -m gguf/airo-media-actions-smollm2-135m-merged-f16.gguf \
  -p $'### Instruction\nTranslate the Airo TV user request into a media action JSON object. Output JSON only. Do not answer conversationally.\n\n### Input\nShow Hindi news\n\n### Response\n' \
  -n 128 \
  --temp 0 \
  --no-display-prompt \
  -no-cnv
```

Base plus LoRA also works:

```bash
llama-completion \
  -m smollm2-135m-instruct-f16.gguf \
  --lora gguf/airo-media-actions-lora-f16.gguf \
  -p "$PROMPT" \
  -n 128 \
  --temp 0 \
  --no-display-prompt \
  -no-cnv
```

Do not use `llama-cli` chat mode for this adapter; it can wrap prompts as
conversation turns and produce malformed schema output.

## Edge Runtime Configuration

For `slm_edge_intelligence` / `edge-intent`:

```bash
export EDGE_INTELLIGENCE_INTENT_BACKEND=llama.cpp+rule
export EDGE_INTELLIGENCE_LLAMA_CPP_BIN=/path/to/llama-completion
export EDGE_INTELLIGENCE_INTENT_MODEL=/path/to/airo-media-actions-smollm2-135m-merged-f16.gguf
```

Or, when using base plus LoRA:

```bash
export EDGE_INTELLIGENCE_INTENT_BACKEND=llama.cpp+rule
export EDGE_INTELLIGENCE_LLAMA_CPP_BIN=/path/to/llama-completion
export EDGE_INTELLIGENCE_INTENT_MODEL=/path/to/smollm2-135m-instruct-f16.gguf
export EDGE_INTELLIGENCE_INTENT_LORA=/path/to/airo-media-actions-lora-f16.gguf
```

The hybrid backend falls back to the Rust rule backend if local model output is
invalid or low confidence.

## Evaluation

Strict eval on 500 generated media-action examples:

```text
Rule intent accuracy: 1.000
SLM intent accuracy: 1.000
SLM constraint exact accuracy: 1.000
```

No SLM failures were observed in `reports/airo_media_actions_rule_vs_slm.json`.
