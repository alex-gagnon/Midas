"""Input validation helpers for Midas MCP tool parameters."""

import re
from datetime import date as _date
from pathlib import Path

from src.calculators.budget_models import MODELS

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def validate_date(s: str) -> None:
    """Raise ValueError if *s* is not a valid YYYY-MM-DD date string."""
    if not _DATE_RE.match(s):
        raise ValueError(
            f"Invalid date {s!r} — expected format YYYY-MM-DD (e.g. '2024-01-31')"
        )
    # Regex ensures the structural format; fromisoformat catches out-of-range
    # values such as month 13 or day 32.
    try:
        _date.fromisoformat(s)
    except ValueError:
        raise ValueError(
            f"Invalid date {s!r} — expected format YYYY-MM-DD (e.g. '2024-01-31')"
        )


def validate_model(key: str) -> None:
    """Raise ValueError if *key* is not a recognised budget model key."""
    if key not in MODELS:
        valid = ", ".join(sorted(MODELS))
        raise ValueError(
            f"Unknown budget model {key!r} — valid options are: {valid}"
        )


def validate_data_dir(path: Path) -> None:
    """Raise ValueError if *path* is not a non-empty directory."""
    if not path.exists():
        raise ValueError(f"Data directory does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Data directory path is not a directory: {path}")
    if not any(path.iterdir()):
        raise ValueError(f"Data directory is empty: {path}")


def validate_account_id(s: str) -> None:
    """Raise ValueError if *s* contains characters outside [A-Za-z0-9_]."""
    if not _ACCOUNT_ID_RE.match(s):
        raise ValueError(
            f"Invalid account_id {s!r} — only letters, digits, and underscores are allowed"
        )
