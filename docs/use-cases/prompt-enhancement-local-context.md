# Use Case: Prompt Enhancement and Local Context Augmentation

## Summary

Train or tune a small language model to sit before a larger model as a prompt optimizer. The SLM rewrites short, messy, ambiguous user inputs into structured prompts and injects relevant local context from files, terminal output, git diffs, editor state, and project metadata.

This is useful for coding assistants, support tools, enterprise copilots, and any workflow where users often provide incomplete instructions.

For coding tools, this pattern is Local Context Augmentation: local background collectors gather relevant workspace state and the SLM assembles a clean, scoped prompt for the downstream model.

## Target Outcomes

- Rewrite raw user input into a clear instruction.
- Correct typos and ambiguous wording without changing intent.
- Add missing structure such as role, objective, context, and constraints.
- Compress long prompts before sending them to a more expensive model.
- Inject local workspace context automatically.
- Route prompts to the right downstream model or tool.
- Reduce user copy-paste of context.
- Keep sensitive local code context under explicit control.

## Example

Raw user input:

```text
Fix the timeout bug.
```

Augmented prompt:

```markdown
## Role
You are a TypeScript backend engineer.

## Objective
Fix the timeout bug in `src/auth/session.ts`.

## Context
- Active file: `src/auth/session.ts`
- Error: `TokenExpiredError: jwt expired`
- Relevant config: JWT expiration is `15m`
- Recent git diff touches session validation logic

## Constraints
Handle expired tokens gracefully. Do not change unrelated authentication behavior.
```

## Data Sources

- Raw user queries
- Enhanced prompt examples
- Active editor file and selected code
- Terminal errors
- Recent git diffs
- Project README and architecture notes
- AST-derived symbols, imports, and call graph
- Local search results from `ripgrep`, Tree-sitter, or embeddings

## Local Context Collectors

| Layer | Tool / Technology | Purpose |
|---|---|---|
| Orchestration | LangChain, LlamaIndex, custom scripts | Chain data gatherers and prompt assembly steps. |
| Context extraction | Tree-sitter, language servers | Parse local code files and identify functions, classes, imports, and symbols. |
| Fast search | `ripgrep`, file indexes | Find exact references and error strings quickly. |
| Semantic search | LanceDB, Chroma, local embeddings | Retrieve conceptually related files or docs. |
| Prompt routing | LiteLLM or custom router | Send the final prompt to the right local or cloud model. |
| Environment state | Terminal logs, test output, git diff | Add live debugging and change context. |

## Training Format

```json
{
  "instruction": "Rewrite the raw user request into a structured coding prompt using the provided local context.",
  "input": "User request: fix auth bug\nActive file: src/auth/session.ts\nTerminal error: TokenExpiredError: jwt expired\nRecent diff: changed refresh-token flow",
  "output": "## Role\nYou are a backend engineer working on authentication.\n\n## Objective\nFix the expired-token handling bug in src/auth/session.ts.\n\n## Context\nThe terminal shows TokenExpiredError during session verification. Recent changes touched refresh-token flow.\n\n## Constraints\nDo not alter unrelated login behavior. Add or update tests for expired-token handling."
}
```

## Augmented Prompt Anatomy

1. User says: `Fix the user timeout bug.`
2. Local collectors extract:
   - Active file: `src/auth/session.ts`
   - Relevant config: `config/jwt.json`
   - Terminal error: `TokenExpiredError: jwt expired`
   - Git history: recent changes touched session validation
3. Prompt SLM emits a bounded instruction:

```markdown
You are a TypeScript backend engineer. Fix a timeout bug in the active file.

[CONTEXT - ACTIVE FILE]
File: src/auth/session.ts
The error occurs during session verification.

[CONTEXT - LOCAL ENVIRONMENT]
- Error log: TokenExpiredError: jwt expired
- Active configuration: JWT expiration is 15m

[INSTRUCTION]
Modify session verification to catch expired-token failures and trigger refresh-token handling. Do not alter unrelated authentication logic.
```

## Model Tasks

- Prompt cleanup
- Prompt expansion
- Prompt compression
- Intent classification
- Context selection
- Tool routing
- Final prompt assembly

## Blueprint-Guided Prompting

Prompt enhancement should use reusable blueprints for repeated task families. A stronger model can generate the blueprint offline, then the local SLM uses that blueprint at inference time.

Example blueprint families:

- Debugging request to scoped engineering prompt
- Feature request to implementation prompt
- Terminal error to diagnostic prompt
- Code review request to review checklist prompt

The prompt template should also be searched per SLM, because small models can be sensitive to the ordering of task description, examples, local context, output schema, and blueprint.

See [Blueprints and Prompt Template Search for SLMs](../research/blueprints-and-template-search.md).

## Evaluation

- Intent preservation score
- Format compliance
- Context relevance
- Token reduction for compression tasks
- Downstream model success rate
- Human preference ranking between raw and enhanced prompts

## Integration

The SLM runs locally before the main model:

```text
User Input -> Local Context Collectors -> Prompt SLM -> Main LLM/Tool -> Final Output
```

Use fast local inference when privacy matters. Use a larger cloud model only after the prompt has been cleaned, scoped, and compressed.

## Controls

- Keep source snippets bounded by relevance and token budget.
- Prefer exact search and AST links before embeddings for code references.
- Strip secrets from terminal logs and environment context.
- Ask for confirmation before sending sensitive local files to a cloud model.
- Preserve the user's original intent and avoid answering during prompt rewriting.

## First Milestone

Create `data/processed/prompt_enhancement_sft.jsonl` with 500 to 1,000 examples of raw user request plus local context to enhanced prompt.

## References from Source Notes

- [Tree-sitter beginner guide](https://medium.com/@shreshthg30/a-beginners-guide-to-tree-sitter-6698f2696b48)
- [Context engineering for agents](https://www.sitepoint.com/context-engineering-for-agents/)
- [Local RAG and private documents](https://www.sitepoint.com/local-rag-private-documents/)
- [What is LlamaIndex?](https://www.digitalocean.com/resources/articles/what-is-llamaindex)
