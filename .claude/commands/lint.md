# /lint

Run ruff and fix all violations.

## Steps

1. Run ruff with auto-fix: `.venv/Scripts/ruff check --fix src/ tests/`
2. Manually fix any remaining violations ruff cannot auto-fix
3. Confirm zero violations: `.venv/Scripts/ruff check src/ tests/`

## Notes

- Ruff config lives in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`
- Rules: `E` (pycodestyle), `F` (pyflakes), `I` (isort), `UP` (pyupgrade); line length 100
- Do NOT run git commands
