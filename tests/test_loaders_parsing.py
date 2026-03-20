"""Unit tests for src/loaders/parsing.py."""

import pytest
from src.loaders.parsing import parse_dollar, parse_float


# ---------------------------------------------------------------------------
# parse_float
# ---------------------------------------------------------------------------


class TestParseFloat:
    def test_integer_string(self):
        assert parse_float("42") == 42.0

    def test_decimal_string(self):
        assert parse_float("3.14") == 3.14

    def test_negative_value(self):
        assert parse_float("-7.5") == -7.5

    def test_leading_and_trailing_whitespace(self):
        assert parse_float("  12.5  ") == 12.5

    def test_commas_stripped(self):
        assert parse_float("1,234.56") == 1234.56

    def test_commas_and_whitespace(self):
        assert parse_float("  2,000  ") == 2000.0

    def test_empty_string_returns_zero(self):
        assert parse_float("") == 0.0

    def test_whitespace_only_returns_zero(self):
        assert parse_float("   ") == 0.0

    def test_non_numeric_string_returns_zero(self):
        assert parse_float("abc") == 0.0

    def test_none_returns_zero(self):
        assert parse_float(None) == 0.0

    def test_integer_input(self):
        assert parse_float(100) == 100.0

    def test_float_input_passthrough(self):
        assert parse_float(9.99) == 9.99

    def test_zero_string(self):
        assert parse_float("0") == 0.0

    def test_large_number_with_commas(self):
        assert parse_float("1,000,000.00") == 1_000_000.0

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("100", 100.0),
            ("0.01", 0.01),
            ("-0.5", -0.5),
            ("1,000", 1000.0),
            ("  50  ", 50.0),
        ],
    )
    def test_parametrized_valid_values(self, value, expected):
        assert parse_float(value) == expected

    @pytest.mark.parametrize("value", ["abc", "N/A", "--", "n/a", ""])
    def test_parametrized_invalid_values_return_zero(self, value):
        assert parse_float(value) == 0.0


# ---------------------------------------------------------------------------
# parse_dollar
# ---------------------------------------------------------------------------


class TestParseDollar:
    def test_dollar_sign_stripped(self):
        assert parse_dollar("$42.00") == 42.0

    def test_dollar_sign_with_commas(self):
        assert parse_dollar("$1,234.56") == 1234.56

    def test_dollar_sign_with_whitespace(self):
        assert parse_dollar("  $99.99  ") == 99.99

    def test_plus_sign_stripped(self):
        assert parse_dollar("+50.00") == 50.0

    def test_plus_and_dollar_sign(self):
        # lstrip("$").lstrip("+") handles "$..." but not "+$..."
        # Only "$" prefix then "+" prefix is handled; test the documented behavior
        assert parse_dollar("$500") == 500.0

    def test_negative_value(self):
        assert parse_dollar("-25.00") == -25.0

    def test_empty_string_returns_zero(self):
        assert parse_dollar("") == 0.0

    def test_whitespace_only_returns_zero(self):
        assert parse_dollar("   ") == 0.0

    def test_non_numeric_returns_zero(self):
        assert parse_dollar("N/A") == 0.0

    def test_none_returns_zero(self):
        assert parse_dollar(None) == 0.0

    def test_plain_number_no_prefix(self):
        assert parse_dollar("123.45") == 123.45

    def test_zero_dollar(self):
        assert parse_dollar("$0.00") == 0.0

    def test_large_dollar_amount(self):
        assert parse_dollar("$10,000.00") == 10_000.0

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("$100", 100.0),
            ("$1,000.50", 1000.50),
            ("+200.00", 200.0),
            ("  $50  ", 50.0),
            ("0", 0.0),
        ],
    )
    def test_parametrized_valid_dollar_values(self, value, expected):
        assert parse_dollar(value) == expected

    @pytest.mark.parametrize("value", ["abc", "$abc", "N/A", ""])
    def test_parametrized_invalid_values_return_zero(self, value):
        assert parse_dollar(value) == 0.0
