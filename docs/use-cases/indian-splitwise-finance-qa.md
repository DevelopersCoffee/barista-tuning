# Use Case: Indian Splitwise-Style Finance QA

## Summary

Train an SLM for a Splitwise-like app that can parse informal Indian expense messages, clean receipt OCR, and answer questions over local spend, settlement, and investment data.

The model should not memorize user finance records. It should convert messy natural language and OCR text into safe structured commands, JSON, or read-only SQL that the app executes against a secure local database.

The training strategy is domain adaptation, not open-ended chat training. The model should learn a small number of precise operational modes and return machine-checkable outputs.

## Target Outcomes

- Parse informal Indian expense messages into app command JSON.
- Extract receipt entities from OCR text.
- Convert finance questions into read-only SQL or structured query plans.
- Explain balances, settlements, and category-level spend.
- Support Indian context such as UPI, GPay, PhonePe, Paytm, Zomato, Swiggy, Blinkit, Zepto, kirana stores, society maintenance, and INR notation.

## Core Modes

### Expense Command Parsing

Input:

```text
Amit paid ₹900 for Swiggy. Split equally with Rahul and Priya.
```

Output:

```json
{
  "intent": "ADD_EXPENSE",
  "currency": "INR",
  "total_amount": 900,
  "paid_by": "Amit",
  "split_type": "EQUAL",
  "involved_users": ["Amit", "Rahul", "Priya"]
}
```

### Receipt OCR Cleanup

Goal: take raw OCR text from a restaurant receipt, payment screenshot, or uploaded bill and output normalized JSON.

Input:

```text
PUNJAB GRILL MUMBAI 1x Butter Chicken 650 3x Butter Naan 240 CGST 2.5% SGST 2.5% Total 934.50
```

Output:

```json
{
  "intent": "PARSE_RECEIPT",
  "merchant": "Punjab Grill, Mumbai",
  "items": [
    {"name": "Butter Chicken", "quantity": 1, "price": 650},
    {"name": "Butter Naan", "quantity": 3, "price": 240}
  ],
  "tax_cgst": 22.25,
  "tax_sgst": 22.25,
  "grand_total": 934.5
}
```

### Finance Question to Query

Goal: convert questions about group expenses, individual balances, settlements, or investments into precise read-only database queries.

Input:

```text
How much does Rahul owe me for groceries this month?
```

Output:

```sql
SELECT SUM(amount)
FROM group_balances
WHERE debtor = 'Rahul'
  AND creditor = current_user
  AND category = 'groceries'
  AND created_at >= DATE_TRUNC('month', CURRENT_DATE);
```

### Investment Query Generation

Input:

```text
Show my total investment spend in mutual funds this month.
```

Output:

```sql
SELECT SUM(amount)
FROM investments
WHERE user_id = current_user
  AND asset_class = 'Mutual Fund'
  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE);
```

## Base Model Options

- `Qwen2.5-Coder-7B` or `Qwen2.5-Coder-3B`: strong fit for JSON and text-to-SQL.
- `Llama-3.2-3B`: useful when mobile or edge deployment is the main constraint.
- `Phi-4` or `Phi-3.5-mini`: useful for compact reasoning and arithmetic-heavy split logic.

The first training target should be a 3B to 7B instruct model with LoRA or QLoRA. For mobile deployment, train first, then evaluate whether a smaller quantized model still passes schema and arithmetic tests.

## Data Sources

- Synthetic Indian expense conversations
- Receipt OCR text
- App schema examples
- Category taxonomy
- UPI/payment metadata
- User-approved anonymized transactions
- Zomato or restaurant menu data for merchant/item vocabulary

Recommended initial dataset size: 5,000 to 20,000 synthetic and reviewed examples, split across receipt parsing, expense command parsing, and query generation.

## Training Format

```json
{
  "instruction": "Parse this informal Indian expense sharing query into structured app command JSON.",
  "input": "Add 1200 bucks for Zomato paid by Sneha split with Amit and Rahul",
  "output": "{\"intent\":\"ADD_EXPENSE\",\"currency\":\"INR\",\"total_amount\":1200,\"paid_by\":\"Sneha\",\"split_type\":\"EQUAL\",\"involved_users\":[\"Sneha\",\"Amit\",\"Rahul\"]}"
}
```

Receipt extraction example:

```json
{
  "instruction": "Extract transaction data from this raw receipt text.",
  "input": "CAFE COFFEE DAY MUMBAI 03/07/2026 2x Cappuccino 440.00 Total: 440.00 GST 5% Included",
  "output": "{\"merchant\":\"Cafe Coffee Day\",\"date\":\"2026-07-03\",\"currency\":\"INR\",\"total\":440.00,\"items\":[{\"name\":\"Cappuccino\",\"quantity\":2,\"price\":220.00}]}"
}
```

## Training Strategy

- Use QLoRA when GPU memory is limited.
- Use 4-bit quantization during training for consumer GPU feasibility.
- Target attention modules such as `q_proj`, `k_proj`, `v_proj`, and `o_proj`.
- Start with learning rate `2e-4`, then tune based on validation loss and exact-output accuracy.
- Keep validation examples structurally different from generated training templates.
- Measure exact JSON validity and SQL safety before conversational answer quality.

## Corpus-Grounded Synthetic Data

Use a CRAFT-style generation loop to reduce repetitive fully synthetic examples:

1. Write a small set of high-quality few-shot examples.
2. Retrieve similar real corpus rows from menu, merchant, receipt, and transaction sources.
3. Ask an instruction-tuned model to convert retrieved records into app-specific JSONL examples.
4. Filter invalid JSON, duplicate examples, arithmetic mistakes, and unsupported merchant/item claims.

For this repo, `data/raw/Zomato_Menu_Scraped.xlsx` can provide realistic Indian restaurant, category, item, and price vocabulary for expense and receipt examples.

See [CRAFT Synthetic Dataset Generation](../research/craft-synthetic-dataset-generation.md).

## App Architecture

```text
User Input / Receipt Image
  -> Local OCR, such as Tesseract or Apple Vision
  -> Financial SLM
  -> Structured JSON or read-only SQL
  -> Secure local database
  -> Deterministic formatter
  -> Natural language answer
```

The SLM should not directly update balances. For write-like flows, it should emit a validated command payload that application code executes after user confirmation.

## Guardrails

- Use read-only SQL for answer queries.
- Validate generated JSON against app schemas.
- Block `UPDATE`, `DELETE`, `DROP`, `ALTER`, and other write SQL.
- Resolve relative dates outside the model before query execution.
- Ask for clarification when payer, participants, amount, or split rule is ambiguous.
- Use a dedicated validation schema before adding parsed receipt expenses.
- Never allow the model to generate DDL or destructive database statements.

## Evaluation

- JSON schema validity
- Entity extraction F1
- Amount calculation accuracy
- SQL validity
- Read-only safety pass rate
- Answer correctness from database fixtures
- Indian context coverage

## First Milestone

Generate synthetic Indian Splitwise examples for:

- Equal split
- Unequal split
- Itemized split
- Excluded participants
- Settlements
- UPI references
- Receipt parsing
- Spend and investment questions

Then create:

```text
data/processed/indian_splitwise_train.jsonl
data/processed/indian_splitwise_val.jsonl
configs/indian_splitwise.yaml
```

## References from Source Notes

- [A Study on the Advancement of Bill Splitting and Expense Management Applications](https://www.ijprems.com/ijprems-paper/a-study-on-the-advancement-of-bill-splitting-and-expense-management-applications)
- [Qwen models on Hugging Face](https://huggingface.co/Qwen)
- [Meta Llama models on Hugging Face](https://huggingface.co/meta-llama)
- [Microsoft Phi models on Hugging Face](https://huggingface.co/microsoft)
- [TRL documentation](https://huggingface.co/docs/trl/index)
