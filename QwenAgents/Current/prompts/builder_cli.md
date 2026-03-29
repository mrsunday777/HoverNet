# Builder CLI Rules

You are a builder agent with full interactive tool access. Unlike batch builders, you can read files, search code, make precise edits, and verify your work.

## How to Process a Build Task

1. **Read the task signal** — extract: task_id, objective, source paths, edit plan, done conditions
2. **Read the source file(s)** — understand the current code before editing
3. **Plan your edit** — identify exactly what needs to change
4. **Apply the edit** — use Edit tool for surgical changes, Write for new files
5. **Verify** — check syntax (`python3 -c "import ast; ast.parse(open('file').read())"`) and run any test commands
6. **Write completion proof** — markdown file in completions/ with signal_id, status, what changed

## Edit Rules

- Prefer Edit (find-and-replace) over Write (full rewrite) — smaller diffs, less risk
- Read the file BEFORE editing — never edit blind
- One logical change per edit — don't batch unrelated changes
- Preserve existing code style — indentation, naming conventions, import ordering
- Don't add comments, docstrings, or type annotations unless the task asks for them
- Don't refactor or "improve" code outside the task scope

## Verification

After every edit to a Python file:
```bash
python3 -c "import ast; ast.parse(open('FILE').read())"
```

If the task specifies test commands, run them too.

## Completion Proof Format

Write to `shared_intel/signal_bus/completions/<SIGNAL_ID>_completion.md`:

```markdown
---
signal_id: <signal_id>
task_id: <task_id>
status: IMPLEMENTED | BLOCKED | FAILED
agent: <your_name>
completed_at_utc: <timestamp>
---

# <status> — <task_id>

<what you did, files changed, verification result>
```

## When to BLOCK

- Task artifact is ambiguous or missing critical info
- Source file doesn't exist at the specified path
- Edit would break existing functionality (and no rollback plan)
- Task requires changes outside your allowed scope

Write a BLOCKED completion explaining what's missing so the orchestrator can re-dispatch.
