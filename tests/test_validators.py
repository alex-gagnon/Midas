"""Unit tests for src/validators.py."""

import pytest

from src.validators import (
    validate_account_id,
    validate_data_dir,
    validate_date,
    validate_model,
)

# ---------------------------------------------------------------------------
# validate_date
# ---------------------------------------------------------------------------


class TestValidateDate:
    @pytest.mark.parametrize(
        "good",
        [
            "2024-01-31",
            "2026-03-19",
            "2000-12-01",
            "1999-01-01",
        ],
    )
    def test_valid_dates_pass(self, good):
        validate_date(good)  # must not raise

    @pytest.mark.parametrize(
        "bad",
        [
            "2024/01/31",  # slashes
            "01-31-2024",  # wrong order
            "2024-1-31",  # single-digit month
            "2024-01-3",  # single-digit day
            "20240131",  # no separators
            "2024-13-01",  # month 13 (regex only; structural check)
            "",  # empty string
            "not-a-date",
            "2024-01",  # missing day
        ],
    )
    def test_invalid_dates_raise_value_error(self, bad):
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            validate_date(bad)

    def test_error_message_includes_bad_value(self):
        with pytest.raises(ValueError, match="'bad-value'"):
            validate_date("bad-value")


# ---------------------------------------------------------------------------
# validate_model
# ---------------------------------------------------------------------------


class TestValidateModel:
    @pytest.mark.parametrize("key", ["50_30_20", "70_20_10", "80_20", "zero_based"])
    def test_all_known_models_pass(self, key):
        validate_model(key)  # must not raise

    @pytest.mark.parametrize(
        "bad",
        [
            "60_30_10",
            "50/30/20",
            "",
            "ZERO_BASED",  # case-sensitive
            "zero based",
        ],
    )
    def test_unknown_model_raises_value_error(self, bad):
        with pytest.raises(ValueError):
            validate_model(bad)

    def test_error_message_lists_valid_options(self):
        with pytest.raises(ValueError, match="50_30_20"):
            validate_model("bad_model")


# ---------------------------------------------------------------------------
# validate_data_dir
# ---------------------------------------------------------------------------


class TestValidateDataDir:
    def test_valid_non_empty_dir_passes(self, tmp_path):
        (tmp_path / "some_file.csv").write_text("data")
        validate_data_dir(tmp_path)  # must not raise

    def test_nonexistent_path_raises(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            validate_data_dir(missing)

    def test_file_path_raises(self, tmp_path):
        f = tmp_path / "file.csv"
        f.write_text("data")
        with pytest.raises(ValueError, match="not a directory"):
            validate_data_dir(f)

    def test_empty_dir_raises(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="empty"):
            validate_data_dir(empty)

    def test_sample_data_dir_passes(self, sample_data_dir):
        validate_data_dir(sample_data_dir)  # real fixture must not raise


# ---------------------------------------------------------------------------
# validate_account_id
# ---------------------------------------------------------------------------


class TestValidateAccountId:
    @pytest.mark.parametrize(
        "good",
        [
            "chk_001",
            "inv001",
            "ABC",
            "a",
            "A1B2C3",
            "account_id_123",
            "UPPER_LOWER_123",
        ],
    )
    def test_valid_ids_pass(self, good):
        validate_account_id(good)  # must not raise

    @pytest.mark.parametrize(
        "bad",
        [
            "chk-001",  # hyphen
            "inv 001",  # space
            "acc@bank",  # @
            "acc.id",  # period
            "",  # empty string
            "id/path",  # slash
            "id\x00",  # null byte
        ],
    )
    def test_invalid_ids_raise_value_error(self, bad):
        with pytest.raises(ValueError, match="letters, digits, and underscores"):
            validate_account_id(bad)

    def test_error_includes_bad_value(self):
        with pytest.raises(ValueError, match="'bad-id'"):
            validate_account_id("bad-id")
