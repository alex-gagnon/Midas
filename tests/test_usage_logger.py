"""Unit tests for src/usage_logger.py."""

import json
from pathlib import Path

import pytest

from src.usage_logger import (
    SAFE_PARAMS,
    _is_sample,
    _redact,
    _redact_param,
    _safe_args,
    log_tool_call,
)

# ---------------------------------------------------------------------------
# _is_sample
# ---------------------------------------------------------------------------


class TestIsSample:
    @pytest.mark.parametrize("path", [
        Path("data/sample"),
        Path("/home/user/data/sample/"),
        Path("C:/Users/Alex/projects/midas/data/sample"),
        Path("data/SAMPLE"),    # case-insensitive
        Path("my_sample_data"),
    ])
    def test_sample_paths_return_true(self, path):
        assert _is_sample(path) is True

    @pytest.mark.parametrize("path", [
        Path("data/real"),
        Path("/home/user/finances"),
        Path("data/production"),
        Path("data/"),
    ])
    def test_non_sample_paths_return_false(self, path):
        assert _is_sample(path) is False


# ---------------------------------------------------------------------------
# _redact
# ---------------------------------------------------------------------------


class TestRedact:
    @pytest.mark.parametrize("value", [
        "hello",
        42,
        3.14,
        True,
        False,
        None,
    ])
    def test_scalars_pass_through(self, value):
        assert _redact(value) == value

    @pytest.mark.parametrize("value", [
        ["a", "list"],
        {"a": "dict"},
        ("a", "tuple"),
        object(),
    ])
    def test_complex_values_redacted(self, value):
        assert _redact(value) == "<redacted>"


# ---------------------------------------------------------------------------
# _redact_param
# ---------------------------------------------------------------------------


class TestRedactParam:
    def test_safe_param_passes_through_in_real_data(self):
        value, masked = _redact_param("start_date", "2026-01-01", is_sample=False)
        assert value == "2026-01-01"
        assert masked is False

    def test_safe_param_passes_through_in_sample_data(self):
        value, masked = _redact_param("start_date", "2026-01-01", is_sample=True)
        assert value == "2026-01-01"
        assert masked is False

    @pytest.mark.parametrize("key", sorted(SAFE_PARAMS))
    def test_all_safe_params_not_masked_with_real_data(self, key):
        value, masked = _redact_param(key, "some_value", is_sample=False)
        assert masked is False

    def test_non_safe_string_param_masked_with_real_data(self):
        value, masked = _redact_param("account_id", "chk_001", is_sample=False)
        assert value == "<masked>"
        assert masked is True

    def test_non_safe_int_param_masked_with_real_data(self):
        value, masked = _redact_param("limit", 100, is_sample=False)
        assert value == "<masked>"
        assert masked is True

    def test_none_value_not_masked_even_with_real_data(self):
        value, masked = _redact_param("account_id", None, is_sample=False)
        assert value is None
        assert masked is False

    def test_non_safe_param_not_masked_with_sample_data(self):
        value, masked = _redact_param("account_id", "chk_001", is_sample=True)
        assert value == "chk_001"
        assert masked is False

    def test_safe_params_set_contains_expected_keys(self):
        assert "start_date" in SAFE_PARAMS
        assert "end_date" in SAFE_PARAMS
        assert "model" in SAFE_PARAMS


# ---------------------------------------------------------------------------
# _safe_args
# ---------------------------------------------------------------------------


class TestSafeArgs:
    def test_empty_args_and_kwargs(self):
        result, any_masked = _safe_args((), {}, is_sample=True)
        assert result == {}
        assert any_masked is False

    def test_kwargs_with_safe_params_in_real_data(self):
        result, any_masked = _safe_args((), {"start_date": "2026-01-01", "model": "50_30_20"}, is_sample=False)
        assert result["start_date"] == "2026-01-01"
        assert result["model"] == "50_30_20"
        assert any_masked is False

    def test_kwargs_with_unsafe_params_masked_in_real_data(self):
        result, any_masked = _safe_args((), {"account_id": "chk_001"}, is_sample=False)
        assert result["account_id"] == "<masked>"
        assert any_masked is True

    def test_positional_args_included_under_positional_key(self):
        result, _ = _safe_args(("arg1", 42), {}, is_sample=True)
        assert "_positional" in result
        assert result["_positional"] == ["arg1", 42]

    def test_positional_complex_args_redacted(self):
        result, _ = _safe_args(({"complex": "dict"},), {}, is_sample=True)
        assert result["_positional"] == ["<redacted>"]

    def test_any_masked_false_when_no_masking_occurs(self):
        _, any_masked = _safe_args((), {"start_date": "2026-01-01"}, is_sample=False)
        assert any_masked is False

    def test_any_masked_true_when_any_param_masked(self):
        _, any_masked = _safe_args(
            (),
            {"start_date": "2026-01-01", "account_id": "chk_001"},
            is_sample=False,
        )
        assert any_masked is True


# ---------------------------------------------------------------------------
# log_tool_call decorator
# ---------------------------------------------------------------------------


class TestLogToolCall:
    def test_decorated_function_returns_normally(self, tmp_path):
        sample_dir = Path("data/sample")

        @log_tool_call(sample_dir)
        def my_tool():
            return {"result": "ok"}

        result = my_tool()
        assert result == {"result": "ok"}

    def test_decorated_function_writes_log_entry(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "usage.jsonl"

        import src.usage_logger as ul
        monkeypatch.setattr(ul, "_LOG_DIR", log_dir)
        monkeypatch.setattr(ul, "_LOG_FILE", log_file)

        sample_dir = Path("data/sample")

        @log_tool_call(sample_dir)
        def my_tool(model="50_30_20"):
            return {"result": "ok"}

        my_tool(model="50_30_20")

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["tool"] == "my_tool"
        assert entry["is_sample"] is True
        assert entry["error"] is None
        assert "ts" in entry
        assert "duration_ms" in entry

    def test_exception_still_logs_error(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "usage.jsonl"

        import src.usage_logger as ul
        monkeypatch.setattr(ul, "_LOG_DIR", log_dir)
        monkeypatch.setattr(ul, "_LOG_FILE", log_file)

        sample_dir = Path("data/sample")

        @log_tool_call(sample_dir)
        def failing_tool():
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError):
            failing_tool()

        entry = json.loads(log_file.read_text().strip())
        assert "Something went wrong" in entry["error"]

    def test_duration_ms_is_positive(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "usage.jsonl"

        import src.usage_logger as ul
        monkeypatch.setattr(ul, "_LOG_DIR", log_dir)
        monkeypatch.setattr(ul, "_LOG_FILE", log_file)

        @log_tool_call(Path("data/sample"))
        def quick_tool():
            return {}

        quick_tool()
        entry = json.loads(log_file.read_text().strip())
        assert entry["duration_ms"] >= 0

    def test_real_data_unsafe_param_sets_args_redacted_flag(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "usage.jsonl"

        import src.usage_logger as ul
        monkeypatch.setattr(ul, "_LOG_DIR", log_dir)
        monkeypatch.setattr(ul, "_LOG_FILE", log_file)

        real_dir = Path("data/real")  # no "sample" in path

        @log_tool_call(real_dir)
        def tool_with_account(account_id=None):
            return {}

        tool_with_account(account_id="chk_001")
        entry = json.loads(log_file.read_text().strip())
        assert entry.get("args_redacted") is True
        assert entry["args"]["account_id"] == "<masked>"

    def test_real_data_safe_params_not_masked(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_file = log_dir / "usage.jsonl"

        import src.usage_logger as ul
        monkeypatch.setattr(ul, "_LOG_DIR", log_dir)
        monkeypatch.setattr(ul, "_LOG_FILE", log_file)

        real_dir = Path("data/real")

        @log_tool_call(real_dir)
        def budget_tool(start_date=None, end_date=None, model="50_30_20"):
            return {}

        budget_tool(start_date="2026-01-01", end_date="2026-01-31", model="70_20_10")
        entry = json.loads(log_file.read_text().strip())
        assert entry["args"]["start_date"] == "2026-01-01"
        assert entry["args"]["end_date"] == "2026-01-31"
        assert entry["args"]["model"] == "70_20_10"
        assert entry.get("args_redacted") is not True

    def test_wraps_preserves_function_name(self):
        @log_tool_call(Path("data/sample"))
        def named_tool():
            return {}

        assert named_tool.__name__ == "named_tool"
