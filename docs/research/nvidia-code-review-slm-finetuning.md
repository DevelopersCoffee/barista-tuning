# Research Note: Fine-Tuned SLMs for Code Review Accuracy

Source: [Fine-Tuning Small Language Models to Optimize Code Review Accuracy](https://developer.nvidia.com/blog/fine-tuning-small-language-models-to-optimize-code-review-accuracy/)

## Why It Matters

This article is highly relevant to the Java Sonar and developer digital twin use case. It describes a practical teacher-student workflow for improving a small model on code review tasks, especially severity rating and explanation generation.

The key result from NVIDIA's write-up: a LoRA fine-tuned Llama 3 8B Instruct model improved code-review severity prediction accuracy by more than 18% over its baseline and outperformed larger models in their reported comparison.

## Core Pattern

Use a large teacher model to create and evaluate task-specific exams for a smaller student model. Then fine-tune the student on a curriculum targeted at the weaknesses found during evaluation.

The loop:

1. Teacher generates an exam from task data and previous student feedback.
2. Student answers the exam.
3. Teacher evaluates answers and identifies weaknesses.
4. Teacher creates a new curriculum focused on those weaknesses.
5. Student is fine-tuned with LoRA or another PEFT method.
6. Repeat until performance stabilizes or budget is reached.

## Code Review Task Shape

For code review severity prediction, the task can be represented as strict JSON:

```json
{
  "question": {
    "code": "<code snippet or diff under review>",
    "review": "<human or generated review comment>"
  },
  "answer": {
    "issue_type": "major"
  }
}
```

Severity labels should be defined up front:

- `critical`: security vulnerability, crash, abrupt exit, data loss, or exploitable bug
- `major`: severe bug that can produce incorrect results
- `minor`: undesired behavior that does not disrupt the whole system
- `trivial`: low-impact comment, docs, style, or formatting concern

## How To Apply It In This Repo

For our Java/Sonar use case, adapt the NVIDIA loop as:

```text
Sonar issues + Java diffs + review comments
  -> teacher exam generation
  -> baseline SLM severity prediction
  -> teacher evaluation and weakness report
  -> targeted curriculum JSONL
  -> LoRA fine-tuning
  -> held-out severity and explanation evaluation
```

Recommended output files:

```text
data/processed/java_code_review_exam.jsonl
data/processed/java_code_review_curriculum.jsonl
reports/java_code_review_eval.json
```

## Training Examples

Severity prediction:

```json
{
  "instruction": "Classify the severity of this Java code review issue.",
  "input": "{\"code\":\"String token = null; return token.length();\",\"review\":\"The code can dereference a null token and crash at runtime.\"}",
  "output": "{\"issue_type\":\"critical\"}"
}
```

Explanation generation:

```json
{
  "instruction": "Explain the severity rating for this Java code review issue.",
  "input": "{\"code\":\"if (amount > limit) approve();\",\"review\":\"The condition appears inverted and may approve over-limit transactions.\",\"issue_type\":\"major\"}",
  "output": "{\"explanation\":\"This is major because the logic can approve transactions that should be rejected, producing incorrect business results without necessarily crashing the system.\"}"
}
```

## Evaluation

Measure two separate capabilities:

- Severity rating accuracy
- Explanation quality and expert alignment

For this repo, use:

- exact label accuracy for `critical`, `major`, `minor`, `trivial`
- macro-F1 to avoid hiding poor performance on rare critical examples
- confusion matrix between adjacent severities
- JSON validity
- explanation rubric score
- human review for high-severity cases

## Relationship To Blueprints

Blueprint prompting should be tried before fine-tuning. If blueprint plus template search does not meet target accuracy, use this teacher-student curriculum loop to create targeted examples for LoRA training.

The combined workflow should be:

```text
baseline prompt
  -> blueprint + template search
  -> teacher-generated exam
  -> weakness-targeted curriculum
  -> LoRA fine-tune
  -> held-out evaluation
```

## Implementation Decision

Adopt this workflow for the Java code-review SLM:

- Start with severity classification and explanation generation.
- Use strict JSON outputs.
- Keep low-severity filtering outside the model.
- Treat teacher-generated labels as draft labels until sampled human review confirms quality.
- Use Sonar issue labels where available as higher-trust ground truth.
