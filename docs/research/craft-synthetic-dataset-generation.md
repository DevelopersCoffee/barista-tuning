# Research Note: CRAFT Synthetic Dataset Generation

Source: [CRAFT Your Dataset: Task-Specific Synthetic Dataset Generation Through Corpus Retrieval and Augmentation](https://arxiv.org/html/2409.02098v1)

## Why It Matters

CRAFT is directly useful for this repo because most SLM use cases here need task-specific JSONL data before training. The paper proposes a practical way to generate that data from a small number of hand-written examples plus a larger raw corpus.

The method is useful when we have raw domain data, such as:

- scraped menu rows
- receipt OCR text
- Jira tickets
- Confluence pages
- Bitbucket commits
- Flyway migrations
- Sonar issues

Instead of asking an LLM to invent all examples from scratch, CRAFT retrieves relevant real corpus documents and asks an instruction-tuned model to transform them into the desired task format.

## Core Pattern

CRAFT stands for Corpus Retrieval and Augmentation for Fine-Tuning.

The loop:

1. Write a few high-quality examples of the target task.
2. Embed those examples.
3. Retrieve similar human-written documents from a corpus.
4. Use an instruction-tuned LLM to convert retrieved documents into task-formatted samples.
5. Filter invalid, low-quality, duplicate, or overly similar samples.
6. Fine-tune the target model on the generated dataset.

## How It Applies Here

### Menu QA

Use `data/raw/Zomato_Menu_Scraped.xlsx` as the raw corpus.

Few-shot examples define the task:

```json
{
  "instruction": "Answer the menu question using only the restaurant menu rows.",
  "input": "Restaurant: Blue Tokai. Question: What cold coffee items are available under 300 INR?",
  "output": "The cold coffee items under 300 INR are ..."
}
```

Retrieved rows provide grounded menu context:

```text
Restaurant_Name, Category, Item_Name, Price
```

The augmentation model converts retrieved rows into training examples for:

- menu question answering
- price comparison
- item lookup
- category summary
- restaurant-specific recommendations

### Indian Splitwise Finance QA

Use synthetic seed examples plus realistic merchant and item corpora:

- Zomato menu rows
- Indian merchant lists
- receipt OCR snippets
- app schema examples

CRAFT helps avoid repetitive fully synthetic examples by grounding generation in real Indian food, merchant, and price vocabulary.

### Java Sonar

Use Sonar issues and Java diffs as the corpus. Few-shot examples define output style for severity labels, explanations, and remediation plans.

### Enterprise Search

Use Jira, Confluence, Bitbucket, and database release notes as corpora. Few-shot examples define router outputs, cited answers, or text-to-SQL formats.

## Dataset Builder Design

Recommended pipeline:

```text
few_shots.jsonl
  -> embed few-shot examples
  -> embed corpus records
  -> retrieve top-k similar records
  -> synthesize task samples
  -> validate JSON/schema
  -> deduplicate
  -> split train/val
```

Suggested repo outputs:

```text
data/processed/<task>_few_shots.jsonl
data/processed/<task>_retrieved_context.jsonl
data/processed/<task>_synthetic_train.jsonl
data/processed/<task>_synthetic_val.jsonl
reports/<task>_craft_filter_report.json
```

## Quality Filters

CRAFT emphasizes filtering generated samples before training. For this repo, use:

- valid JSON check
- required key check
- schema validation
- minimum input/output length
- duplicate removal
- fuzzy similarity filtering against few-shots and generated samples
- source coverage report
- train/validation leakage check

For SQL tasks, also add:

- parseability check
- read-only SQL check
- known table/column validation

For menu QA, add:

- item names must exist in retrieved context
- prices must match source rows
- answer must not cite restaurants outside the retrieved context

## Retrieval Notes

The paper notes that retrieval should balance:

- similarity to individual few-shot examples
- similarity to the average of all few-shot examples

This matters because using only one strategy can over-focus on a dominant topic and reduce diversity. For our data builders, use both:

```text
50% individual few-shot top-k retrieval
50% averaged few-shot embedding retrieval
```

## Training Notes

The paper evaluates dataset sizes from 100 to 25,000 synthetic examples. For this repo:

- start with 100 examples to validate the task and filters
- move to 500 examples for first LoRA smoke test
- move to 5,000+ examples only after evaluation shows the generated labels are useful

## Implementation Decision

Adopt CRAFT as the default dataset-generation pattern when we have raw domain corpora but limited labeled examples.

For the current repo, the first practical CRAFT target should be:

```text
Zomato menu rows -> synthetic menu question-answering JSONL
```

This turns the existing workbook into training and evaluation data without relying entirely on invented examples.
