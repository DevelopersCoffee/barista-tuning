# Use Case: Edge Task-Specific SLMs

## Summary

Create small, task-specific models that can run locally on laptops, phones, or edge devices. The model is trained for a narrow workflow, compressed through quantization, and packaged for local inference.

This pattern is useful for privacy-sensitive tasks such as personal finance parsing, prompt enhancement, offline support assistants, mobile actions, and local document question answering.

## Target Outcomes

- Run inference offline or with minimal network dependency.
- Keep private user data on-device.
- Reduce latency and serving cost.
- Specialize a small model for one task instead of relying on a large general model.
- Package the model for Ollama, llama.cpp, ONNX, LiteRT, or mobile runtimes.

## Candidate Tasks

- Receipt OCR cleanup
- Indian expense command parsing
- Prompt enhancement
- Local coding context routing
- Form filling
- Support ticket triage
- Mobile tool calling
- Offline menu question answering

## Model Generation Pipeline

1. Pick a small open base model.
2. Build a task-specific JSONL dataset.
3. Fine-tune with LoRA or QLoRA.
4. Evaluate against strict task fixtures.
5. Merge or package adapters when needed.
6. Quantize to 8-bit or 4-bit.
7. Convert to the target runtime format.
8. Ship with task-specific prompts and validation code.

## Training Format

```json
{
  "instruction": "Convert this mobile user request into a safe app action JSON.",
  "input": "Split yesterday's Zomato dinner equally with Amit and Priya. I paid 1500.",
  "output": "{\"action\":\"ADD_EXPENSE\",\"merchant\":\"Zomato\",\"amount\":1500,\"currency\":\"INR\",\"paid_by\":\"current_user\",\"participants\":[\"current_user\",\"Amit\",\"Priya\"],\"split_type\":\"EQUAL\"}"
}
```

## Runtime Options

- Desktop: Ollama, llama.cpp, vLLM
- Mobile: MLC LLM, MediaPipe, LiteRT, ONNX Runtime Mobile
- Browser: WebGPU runtimes for very small models
- Serverless edge: quantized model behind a narrow API

## Guardrails

- Validate all structured outputs.
- Keep task prompts narrow.
- Use deterministic decoding for command generation.
- Put business logic outside the model.
- Run privacy review before using real user data.
- Keep fallback paths for unsupported requests.

## Evaluation

- Exact JSON validity
- Intent classification accuracy
- Slot extraction accuracy
- Latency on target device
- Memory footprint
- Battery impact for mobile
- Offline success rate

## First Milestone

Choose one task and one target runtime:

```text
Task: Indian expense command parsing
Runtime: Ollama or llama.cpp
Model: 1B to 3B instruct model
Metric: valid command JSON and correct split amount
```
