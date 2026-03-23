---
name: verify
description: "Run the standard quality gate: pytest + ruff. Reports pass/fail counts and fixes lint errors if found. Use after code changes or before committing."
---

Run the two standard checks in order:

## 1. Tests

```bash
uv run pytest tests/ -q
```

Report: total passed, failed, any error output.

## 2. Lint

```bash
uv run ruff check src/
```

If lint errors are found, fix them directly (ruff errors are typically minor — unused imports, whitespace, etc.) then re-run to confirm clean.

## Pass criteria

- 0 test failures
- 0 ruff errors

## On failure

- **Test failures**: Read the failure output carefully. If it's a broken import or a missing file, check whether a recent deletion caused it. Fix the test or the source, then re-run.
- **Lint errors**: Apply `ruff check --fix src/` for auto-fixable issues, then handle remaining ones manually.

Always report final counts to the user.
