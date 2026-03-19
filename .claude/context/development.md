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
