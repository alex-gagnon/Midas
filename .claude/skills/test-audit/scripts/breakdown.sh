#!/usr/bin/env bash
# Test count broken down by class, sorted descending
uv run pytest tests/ -q --collect-only 2>/dev/null | grep "::" | sed 's/::test_.*//' | sort | uniq -c | sort -rn
