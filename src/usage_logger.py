"""Structured usage logging for Midas MCP tool calls."""

import functools
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "usage.jsonl"

# Params that are safe to log in plain text even with real data.
SAFE_PARAMS: frozenset[str] = frozenset({"start_date", "end_date", "model"})


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(exist_ok=True)


def _write_entry(entry: dict) -> None:
    _ensure_log_dir()
    with _LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def log_tool_call(data_dir: Path):
    """Decorator factory. Pass the server's DATA_DIR so it's captured per call."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            error = None
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as exc:
                error = str(exc)[:200]
                raise
            finally:
                elapsed = time.monotonic() - start
                is_sample = _is_sample(data_dir)
                safe_args, any_masked = _safe_args(args, kwargs, is_sample)
                entry: dict[str, Any] = {
                    "ts": datetime.now(UTC).isoformat(),
                    "tool": fn.__name__,
                    "args": safe_args,
                    "data_dir": str(data_dir),
                    "is_sample": is_sample,
                    "duration_ms": round(elapsed * 1000, 1),
                    "error": error,
                }
                if not is_sample and any_masked:
                    entry["args_redacted"] = True
                _write_entry(entry)

        return wrapper

    return decorator


def _safe_args(args: tuple, kwargs: dict, is_sample: bool) -> tuple[dict[str, Any], bool]:
    """Merge positional and keyword args into a single dict for logging.

    Returns (merged_dict, any_masked) where any_masked is True if at least one
    value was replaced with '<masked>' due to the real-data redaction policy.
    """
    any_masked = False
    result: dict[str, Any] = {}

    if args:
        # Positional args have no name, so always redact them as complex objects
        # when not sample (they could contain anything).
        redacted = [_redact(a) for a in args]
        result["_positional"] = redacted

    for k, v in kwargs.items():
        redacted_v, masked = _redact_param(k, v, is_sample)
        result[k] = redacted_v
        if masked:
            any_masked = True

    return result, any_masked


def _redact(value: Any) -> Any:
    """Pass through simple scalar values; redact anything complex."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return "<redacted>"


def _redact_param(key: str, value: Any, is_sample: bool) -> tuple[Any, bool]:
    """Return (logged_value, was_masked).

    When using real data, only SAFE_PARAMS are logged as-is.  All other params
    are replaced with '<masked>' regardless of their type.
    """
    if not is_sample and key not in SAFE_PARAMS:
        if isinstance(value, (str, int, float, bool)) and value is not None:
            return "<masked>", True
        # None values are harmless — no data to leak.
        if value is None:
            return None, False
        return "<masked>", True
    return _redact(value), False


def _is_sample(data_dir: Path) -> bool:
    return "sample" in str(data_dir).lower()
