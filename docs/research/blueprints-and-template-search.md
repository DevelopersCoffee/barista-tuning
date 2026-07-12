# Research Note: Blueprints and Prompt Template Search for SLMs

Source: [Enhancing Reasoning Capabilities of Small Language Models with Blueprints and Prompt Template Search](https://arxiv.org/html/2506.08669v1)

## Why It Matters

This paper is directly relevant to this repo because it improves SLM task performance without changing model size or requiring another fine-tuning run.

The core idea is:

1. Use a stronger LLM offline to create reusable reasoning blueprints for a task family.
2. Select or refine the best blueprint for a specific SLM and task.
3. Search across prompt templates because SLMs are sensitive to prompt ordering and formatting.
4. Reuse the chosen blueprint and template at inference time.

This is useful for on-device, local, or cost-sensitive SLM deployments where retraining is expensive or unnecessary.

## Key Concept

A blueprint is a reusable task guide. It is not a one-off chain-of-thought answer. It describes how the SLM should approach a class of related problems.

Example shape:

```text
Task: Convert informal Indian expense text into structured JSON.

Blueprint:
1. Identify the intent: add expense, query balance, settle payment, or parse receipt.
2. Extract participants and payer.
3. Extract amount, currency, merchant, and payment method.
4. Determine split rule: equal, unequal, itemized, excluded participant, or weighted.
5. Return only schema-valid JSON. Ask for clarification if required fields are missing.
```

## How To Apply It In This Repo

Use blueprints before deciding to fine-tune. For each use case, build:

```text
docs/blueprints/<use-case>/<task>.md
configs/templates/<use-case>.yaml
reports/template-search/<use-case>.json
```

Then evaluate:

- baseline prompt
- few-shot prompt
- blueprint prompt
- blueprint plus selected template

Only fine-tune if prompt-level optimization fails to meet the target quality.

## Candidate Blueprint Tasks

### Prompt Enhancement

- Raw request to enhanced prompt
- Local context selection
- Tool routing
- Prompt compression

### Indian Splitwise Finance QA

- Informal text to expense command JSON
- Receipt OCR to normalized receipt JSON
- Finance question to read-only SQL
- Settlement question to query plan

### Java Sonar and Developer Twin

- Java snippet to issue explanation
- Git diff to risk summary
- Sonar issue to remediation plan
- Ticket context to implementation plan

### Federated Enterprise Search

- User question to source-routing JSON
- Tagged context to cited answer
- Jira question to JQL
- Yugabyte question to read-only SQL

## Prompt Template Search

The paper highlights that SLM performance can change significantly based on prompt ordering and style. For our tasks, search over templates such as:

```text
template_a: task_description -> blueprint -> input -> output_schema
template_b: blueprint -> task_description -> output_schema -> input
template_c: output_schema -> task_description -> examples -> input
template_d: examples -> blueprint -> input -> output_schema
```

Measure the same validation set across all templates and select the best per model and task.

## Minimal Evaluation Loop

For each task:

1. Create 50 to 200 validation examples.
2. Create 3 to 8 candidate blueprints.
3. Create 4 to 12 candidate prompt templates.
4. Run deterministic inference.
5. Score with task-specific validators.
6. Save the winning blueprint and template.

Task validators should be strict:

- JSON schema validity for command generation
- SQL parse and read-only checks for text-to-SQL
- citation coverage for enterprise search
- exact label/severity matching for Sonar tasks
- downstream execution success for coding tasks

## Repo Implications

This should become a first-class stage before training:

```text
prepare data -> generate blueprints -> search templates -> evaluate -> train only if needed
```

Recommended future CLI commands:

```bash
slm blueprint generate configs/indian_splitwise.yaml
slm template-search configs/indian_splitwise.yaml
slm evaluate configs/indian_splitwise.yaml --prompt-strategy blueprint
```

## Decision

Adopt blueprint-guided prompting as the default first experiment for every new SLM use case. Fine-tuning remains useful when the model lacks domain vocabulary, output discipline, or schema-specific behavior after blueprint/template optimization.
