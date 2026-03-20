# Midas — Claude Code Guide

## Project overview

Midas is a personal finance MCP (Model Context Protocol) server built with FastMCP. It exposes tools for net worth, budget breakdown, and brokerage performance calculations, backed by CSV data files.

## Running the server

```bash
python main.py
```

Or via the installed script (after `uv pip install -e .`):

```bash
midas
```

Set `MIDAS_DATA_DIR` to point at a custom data directory (defaults to `data/sample/`).

## Context

Detailed reference lives in `.claude/context/`:

- [data-format.md](.claude/context/data-format.md) — CSV schemas and data directory env vars
- [development.md](.claude/context/development.md) — adding tools/loaders, dependencies, build config

## Behavioral rules

- Do NOT stage, commit, or run any git commands unless explicitly asked by the user.
- Do NOT include sensitive data in any file — no institution names, account numbers, ticker symbols, balances, or any other PII. This applies to TODO.md, memory files, context files, comments, and anywhere else. Describe problems generically (e.g. "checking account loader" not the bank's name, "one loader omits cost basis" not the specific loader or symbols).
