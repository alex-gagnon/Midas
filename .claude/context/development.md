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

- `MIDAS_DATA_DIR` — path to a single CSV data directory; defaults to `data/sample/`
- `MIDAS_DATA_ROOT` — path to a root directory containing per-institution subdirectories (activates the composite loader; when set, `MIDAS_DATA_DIR` is ignored)

Optionally, install the `dotenv` extra and create a `.env` file to set variables locally:

```bash
uv pip install -e ".[dotenv]"
cp .env.example .env
```

See `.env.example` at the project root for a template with all recognised variables.
