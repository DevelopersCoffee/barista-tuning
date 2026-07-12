# Use Case: Java Sonar SLM and Developer Digital Twin

## Summary

Train a small language model to understand Java code changes, Sonar-style quality issues, and historical developer behavior. The model should help answer questions, detect likely code quality problems, explain Sonar violations, and eventually propose fixes or follow-up changes in the style of the target codebase.

This use case combines two related capabilities:

1. Java static-analysis assistant: detect and explain bugs, vulnerabilities, code smells, and maintainability issues from Java snippets or diffs.
2. Developer/process digital twin: learn from Git commits, diffs, commit messages, and quality-gate outcomes to predict impact and generate codebase-aligned changes.

## Primary Users

- Java developers who want fast, local code-quality feedback.
- Tech leads reviewing risky changes before merge.
- QA or platform teams tracking SonarQube quality gates.
- Engineering automation agents that generate fixes or pull requests.

## Target Outcomes

- Given Java code, identify likely Sonar-style issues with severity and explanation.
- Given a Git diff, summarize the intent, risk, and likely affected files.
- Given a Sonar violation, generate a codebase-consistent remediation suggestion.
- Given a ticket or change request, generate a patch and commit message in the style of previous commits.
- Given a file or module change, predict related files that may also need updates.

## Non-Goals for v1

- Replacing SonarQube as the source of truth for static analysis.
- Guaranteeing bug-free generated code.
- Training directly on private repositories without access controls and data review.
- Automatically merging generated code without human review.

## Data Sources

### SonarQube Data

Use SonarQube or SonarCloud as the labeled quality source.

Useful fields:

- Project key
- File path
- Rule key
- Issue type: `BUG`, `VULNERABILITY`, `CODE_SMELL`
- Severity
- Message
- Line number or code range
- Status and resolution
- Quality profile
- Quality gate result

### Java Source Data

Use Java files and code snippets around Sonar issue locations.

Useful fields:

- Repository
- Branch or commit SHA
- File path
- Class name
- Method name
- Code snippet
- Surrounding imports and relevant context
- Build tool metadata, such as Maven or Gradle module

### Git History Data

Use commit history to learn change patterns and developer style.

Useful fields:

- Commit SHA
- Author
- Timestamp
- Commit message
- Modified files
- Added and removed lines
- Parsed diff
- Linked ticket or issue ID
- Test files changed
- Sonar quality-gate result after commit

## Training Data Formats

### Sonar Issue Detection Example

```json
{
  "instruction": "Analyze the Java code for Sonar-style quality issues.",
  "input": "public class Data {\n  public void process() {\n    String x = null;\n    System.out.println(x.length());\n  }\n}",
  "output": "Severity: Blocker\nType: Bug\nIssue: NullPointerException risk\nExplanation: The variable x is explicitly assigned null and then dereferenced through x.length().\nSuggested fix: Check for null before dereferencing or avoid assigning null."
}
```

### Diff Risk Review Example

```json
{
  "instruction": "Review this Java diff for quality and regression risk.",
  "input": "Commit message: Add order discount calculation\nDiff:\n--- a/OrderService.java\n+++ b/OrderService.java\n@@\n+ double discount = total * coupon.getPercent();",
  "output": "Risk: Medium\nReason: The new code assumes coupon is non-null and does not validate percent bounds.\nLikely Sonar issues: possible null dereference, missing validation.\nSuggested checks: add null handling, clamp or validate percent, and add unit tests for missing coupon."
}
```

### Developer Twin Example

```json
{
  "instruction": "Generate a commit-style implementation plan from the ticket and recent repository pattern.",
  "input": "Ticket: Add menu item search by category.\nRecent pattern: Controllers delegate to services, services return DTOs, tests use JUnit parameterized cases.",
  "output": "Plan:\n1. Add a category filter method to MenuService.\n2. Expose the filter in MenuController.\n3. Add DTO mapping for category results.\n4. Add parameterized tests for exact category, missing category, and empty result.\nCommit message: Add category-based menu item search"
}
```

## Model Tasks

### v1 Tasks

- Explain Sonar violations from Java snippets.
- Classify issue type and severity.
- Suggest remediation steps.
- Review Java diffs for risk.
- Answer questions over repository quality history.

### v2 Tasks

- Generate patch candidates for selected Sonar violations.
- Predict related files that may need updates.
- Generate commit messages matching project style.
- Draft pull request summaries with risk and test notes.

### v3 Tasks

- Continuous developer/process digital twin updated from Git events.
- Agent-assisted remediation branches.
- Quality-gate-aware pull request automation.

## Pipeline

1. Ingest Java repositories, Sonar issues, and Git history.
2. Extract code snippets and diffs with metadata.
3. Normalize rows into instruction, input, and output JSONL examples.
4. Split by repository, module, or time window to reduce data leakage.
5. Fine-tune an SLM with LoRA or another parameter-efficient method.
6. Evaluate on held-out Sonar issues, diffs, and repository questions.
7. Publish the model artifact or adapter.
8. Integrate into review tools, CLI workflows, or SonarQube plugin workflows.

## Teacher-Student Fine-Tuning Loop

For code review severity and explanation quality, use a teacher-student workflow:

1. A stronger teacher model generates code review exams from Sonar issues, diffs, and review comments.
2. The student SLM predicts severity labels and explanations.
3. The teacher evaluates the student answers and identifies weak areas.
4. A targeted curriculum is generated for those weak areas.
5. The student is fine-tuned with LoRA or another PEFT method.

This mirrors NVIDIA's code-review SLM approach, where a LoRA fine-tuned Llama 3 8B model improved severity prediction accuracy and explanation quality for automated code review. See [Fine-Tuned SLMs for Code Review Accuracy](../research/nvidia-code-review-slm-finetuning.md).

## Evaluation

Use both automated and human review.

Automated metrics:

- Issue type accuracy
- Severity accuracy
- Macro-F1 across severity labels
- Confusion matrix for `critical`, `major`, `minor`, and `trivial`
- Rule-key accuracy, if rule labels are available
- Explanation quality score from rubric-based evaluation
- Fix suggestion pass rate against tests, where patches are generated
- Retrieval accuracy for repository question answering

Human review rubric:

- Correctly identifies the issue
- Avoids false confidence
- Explains the risk in developer-friendly language
- Suggests a safe and minimal fix
- Matches repository conventions
- Does not invent APIs, files, or rules

## Integration Options

### CLI Assistant

Run locally against a Java file, Git diff, or Sonar export.

Example commands:

```bash
slm train configs/java_sonar.yaml
slm evaluate configs/java_sonar.yaml
slm publish configs/java_sonar.yaml
```

### Pull Request Review Bot

Trigger on pull requests:

- Read changed Java files.
- Attach Sonar issues and previous related commits.
- Generate a risk summary.
- Comment only when confidence is high.

### SonarQube Companion

Use SonarQube as the deterministic scanner and the SLM as the explanation/remediation layer:

- SonarQube detects the rule violation.
- SLM explains why it matters in project context.
- SLM suggests a patch or test case.

## Risks and Controls

- Data leakage: split training and eval by time or repository, not random rows only.
- Hallucinated rules: ground outputs in Sonar rule keys and retrieved code context.
- Unsafe patches: require tests and human approval before merge.
- Private code exposure: keep training data and published artifacts private unless reviewed.
- Overfitting to one developer: separate project conventions from individual author habits.

## First Implementation Milestone

Create a dataset builder that converts Sonar and Git exports into JSONL rows:

```text
data/raw/sonar_issues.jsonl
data/raw/git_commits.jsonl
data/processed/java_sonar_sft.jsonl
```

Then add `configs/java_sonar.yaml` and train a first LoRA adapter on:

- Java snippet to Sonar issue explanation
- Git diff to risk summary
- Ticket context to implementation plan

The first useful release should answer: "What is wrong with this Java code or diff, why does it matter, and what should the developer do next?"
