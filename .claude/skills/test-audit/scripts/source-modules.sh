#!/usr/bin/env bash
# List all non-init source modules for cross-referencing against test coverage
find src/ -name "*.py" ! -name "__init__.py" | sort
