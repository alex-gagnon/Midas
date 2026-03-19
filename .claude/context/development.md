# Development Guide

## Adding a new tool

1. Add calculation logic in the relevant `src/calculators/` module.
2. Register it in `src/server.py` with `@mcp.tool()`.
3. Keep tools focused — one responsibility each.

## Adding a new loader

Subclass `BaseLoader` from `src/loaders/base.py` and implement `load_accounts`, `load_transactions`, and `load_holdings`.

## Dependencies

Managed with `uv`. Add packages via:

```bash
uv add <package>
```

Key dependency: `mcp[cli]>=1.0.0` (FastMCP).

## pyproject.toml notes

- Package source is `src/` — the installed package name is `midas` but source lives under `src/`
- Entry point script: `midas = "midas.server:main"` (requires install)

## Environment variables

- `MIDAS_DATA_DIR` — path to the data directory; defaults to `data/sample/`
- Optionally, install the `dotenv` extra and create a `.env` file to set variables locally:

```bash
uv pip install -e ".[dotenv]"
cp .env.example .env
# edit .env to set MIDAS_DATA_DIR and any future secrets
```

See `.env.example` at the project root for a template with all recognised variables.

## Linting

[ruff](https://docs.astral.sh/ruff/) is the project linter and import sorter. Config lives in `pyproject.toml` under `[tool.ruff]`.

```bash
# Check for violations
.venv/Scripts/ruff check src/ tests/

# Auto-fix what ruff can
.venv/Scripts/ruff check --fix src/ tests/
```

Rules enabled: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `UP` (pyupgrade). Line length is 100. Run ruff clean before committing. After auto-fixing, always run the test suite to catch regressions.
