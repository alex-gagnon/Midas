---
name: execute-plan
description: "Executes a written implementation plan using a code-executor + pytest-guardian team. Use when given a plan document with code changes and test requirements."
---

Orchestrate plan execution using a parallel agent team. Follow these steps exactly:

## 1. Create the team

```
TeamCreate { team_name: "...", description: "..." }
```

## 2. Create tasks with dependencies

For each task in the plan, call `TaskCreate`. Then use `TaskUpdate` with `addBlockedBy` to wire up dependencies. Common dependency patterns:
- Test tasks for new modules are blocked by the module creation task
- Verification (pytest + ruff) is blocked by all code and test tasks

## 3. Spawn agents in parallel

Spawn **both agents in a single message** (parallel tool calls):

- **code-executor** — all structural/code changes. Tell it to: claim tasks in order, message pytest-guardian after completing any shared interface (e.g. a new module they need to write tests for), and NOT run git commands or tests.
- **pytest-guardian** — all test file changes and final verification. Tell it to: wait for the code-executor signal before writing tests for new modules, then run `uv run pytest tests/ -q` and `uv run ruff check src/` as the final task, and report results back.

Always include `team_name` and `name` parameters when spawning.

## 4. Coordinate via SendMessage

- When code-executor reports all code tasks done, send pytest-guardian a message to proceed with verification.
- If pytest-guardian reports failures, send code-executor the failure output and ask it to fix.

## 5. Shut down

When the final verification passes, send shutdown requests to both agents in a single message (parallel). Wait for shutdown confirmations before reporting done.

## Reporting

Summarise: what was deleted/created/modified, test count before/after, lint status.
