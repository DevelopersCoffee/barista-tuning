# Use Case: Release-Aware YugabyteDB Text-to-SQL

## Summary

Train an SLM to generate YugabyteDB SQL that respects the active application release. The model learns schema evolution from release notes, Flyway migrations, and database DDL so it avoids tables or columns that do not exist in the target version.

This is useful when application schemas change frequently and users need reliable natural language access to production, staging, or historical release data.

## Target Outcomes

- Generate SQL for the correct release version.
- Avoid outdated tables and columns.
- Use Yugabyte/PostgreSQL-compatible syntax.
- Prefer indexed and bounded queries.
- Explain which schema version the query targets.
- Support spend, investment, incident, and operational queries.

## Data Sources

- Flyway migration scripts
- Release notes
- Git tags
- Database DDL snapshots
- YugabyteDB index definitions
- Application schema documentation
- Query examples from analytics or support teams

## Training Example

```json
{
  "instruction": "Generate a YugabyteDB SQL query based on release v2.5.0. Question: Get user 99's crypto portfolio balance.",
  "context": "Release v2.5.0 schema: table investments(id, user_id, asset_type, sub_category, amount, created_at). Index idx_user_crypto on investments(user_id, sub_category).",
  "output": "SELECT SUM(amount) FROM investments WHERE user_id = 99 AND sub_category = 'crypto';"
}
```

## Production Prompt Pattern

```markdown
You are a YugabyteDB text-to-SQL assistant.
The application is running Production Release: v2.6.2.

Use only this schema:
- spend_logs(id, user_id, amount, merchant_name, category, created_at)
- investments(id, user_id, amount, asset_type, sub_category, created_at)

Rules:
- Return one SELECT query only.
- Do not use older tables or columns.
- Prefer bounded date filters when the user gives a time range.
- Do not modify data.
```

## Flyway Monorepo Dataset Builder

The dataset builder should:

1. Read migration files in Flyway order.
2. Track schema state after each version.
3. Attach release notes or ticket references.
4. Generate synthetic natural language questions for each schema state.
5. Emit JSONL rows with `instruction`, `context`, and `output`.

Output files:

```text
data/raw/flyway_migrations/
data/raw/release_notes/
data/processed/yugabyte_release_text_to_sql.jsonl
```

## Guardrails

- Parse generated SQL before execution.
- Allow only `SELECT`.
- Run `EXPLAIN` before execution.
- Enforce strict query timeout.
- Use a read-only database user.
- Reject unknown tables and columns using live schema introspection.

## Evaluation

- SQL syntax validity
- Schema-version correctness
- Unknown column/table rate
- Read-only safety
- Query result correctness on fixtures
- Explain-plan safety
- Date-range correctness

## First Milestone

Create a Flyway compiler script that converts migration history into schema snapshots:

```text
V1__init.sql -> schema state V1
V2__add_investments.sql -> schema state V2
V3__add_indexes.sql -> schema state V3
```

Then generate 15 to 25 training questions per schema version.
