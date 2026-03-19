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

- [project-structure.md](.claude/context/project-structure.md) — directory layout and file purposes
- [data-format.md](.claude/context/data-format.md) — CSV schemas and `MIDAS_DATA_DIR`
- [development.md](.claude/context/development.md) — adding tools/loaders, dependencies, build config

## Claude directory

`.claude/` organizes AI-assisted development artifacts:

- **commands/** — Custom `/slash-commands` as `.md` files
- **context/** — Domain knowledge and reference material
- **outputs/** — Reports, analyses, and other generated artifacts
- **skills/** — Custom skill definitions for this project

## Behavioral rules

- Do NOT stage, commit, or run any git commands unless explicitly asked by the user.
