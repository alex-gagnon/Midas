#!/usr/bin/env bash
# Total test count summary (last 3 lines of --collect-only output)
uv run pytest tests/ -q --collect-only 2>/dev/null | tail -3
