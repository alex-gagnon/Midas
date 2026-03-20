---
name: refactor
description: "Structured refactor workflow: audit for dead code, duplication, stale files, and misleading logic; then plan and execute cleanup. Use when asked to clean up or refactor a codebase area."
---

Run a structured refactor in two phases: **audit** then **execute**.

## Phase 1 — Audit

Read the relevant source files and identify:

1. **Dead code** — methods/functions that are defined but never called (renamed with `_raw` or `_old`, commented out, or simply unreachable).
2. **Duplication** — identical or near-identical helpers copy-pasted across files (e.g. `_parse_float` in multiple loaders). Extract to a shared module.
3. **Stale files** — data files, env files, or directories that are no longer referenced by production code. Cross-check with actual imports and `os.environ` reads.
4. **Misleading logic** — conditionals or calls that run unconditionally but should be gated (e.g. `validate_x()` that always runs even when `x` is unused).

## Phase 2 — Plan

Write a concise plan listing:
- Files to delete (with reason)
- New files to create (shared utilities)
- Files to modify (with the specific change)
- Test files to update (references to deleted paths, new tests for extracted utilities)

Get confirmation from the user before proceeding if the scope is large.

## Phase 3 — Execute

Use the `execute-plan` skill to run the changes with a code-executor + pytest-guardian team.

## Acceptance criteria

- `uv run pytest tests/ -q` — 0 failures
- `uv run ruff check src/` — 0 lint errors
- No remaining references (imports, `os.path`, string literals) to deleted files
