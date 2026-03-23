"""Tests for core budget calculator behaviour: shape, income, filtering, date range, errors."""

from datetime import date

import pytest

from src.calculators.budget import calculate_budget_breakdown

from ._shared import STANDARD_TRANSACTIONS, _txn


class TestBudgetBreakdownShape:
    def test_percentage_model_keys(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        assert set(result.keys()) == {
            "model",
            "period",
            "income",
            "total_expenses",
            "remaining",
            "breakdown",
        }

    def test_zero_based_model_keys(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="zero_based")
        assert set(result.keys()) == {
            "model",
            "period",
            "income",
            "total_expenses",
            "remaining",
            "on_track",
            "line_items",
        }

    def test_model_info_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        assert result["model"]["key"] == "50_30_20"
        assert result["model"]["name"] == "50/30/20"

    def test_period_none_when_no_dates(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS)
        assert result["period"]["start"] is None
        assert result["period"]["end"] is None

    def test_period_reflects_provided_dates(self):
        sd = date(2026, 3, 1)
        ed = date(2026, 3, 31)
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, start_date=sd, end_date=ed)
        assert result["period"]["start"] == "2026-03-01"
        assert result["period"]["end"] == "2026-03-31"


class TestIncomeCalculation:
    def test_sums_positive_income_transactions(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS)
        assert result["income"] == pytest.approx(7_000.0)

    def test_only_category_income_counted(self):
        # positive amount with non-income category should NOT be counted as income
        txns = [
            _txn("2026-03-01", 3_000.00, "income"),
            _txn("2026-03-01", 1_000.00, "refund"),  # positive but not income
        ]
        result = calculate_budget_breakdown(txns)
        assert result["income"] == pytest.approx(3_000.0)

    def test_zero_income_with_no_income_transactions(self):
        txns = [_txn("2026-03-01", -100.0, "housing")]
        result = calculate_budget_breakdown(txns)
        assert result["income"] == 0.0

    def test_zero_income_produces_zero_pct_in_breakdown(self):
        txns = [_txn("2026-03-01", -100.0, "housing")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        for bucket_name, bucket in result["breakdown"].items():
            assert bucket["actual_pct"] == 0.0, f"{bucket_name} pct should be 0 with zero income"


class TestExpenseFiltering:
    def test_positive_non_income_transactions_excluded_from_expenses(self):
        txns = [
            _txn("2026-03-01", 3_000.00, "income"),
            _txn("2026-03-05", 50.00, "refund"),  # positive, non-income → excluded
            _txn("2026-03-10", -200.00, "groceries"),
        ]
        result = calculate_budget_breakdown(txns)
        assert result["total_expenses"] == pytest.approx(200.0)

    def test_income_category_excluded_from_expenses(self):
        txns = [
            _txn("2026-03-01", 3_000.00, "income"),
            _txn("2026-03-05", -500.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns)
        assert result["total_expenses"] == pytest.approx(500.0)


class TestDateFiltering:
    def _mixed_date_txns(self):
        return [
            _txn("2026-02-01", 3_500.00, "income"),  # Feb
            _txn("2026-02-10", -500.00, "housing"),  # Feb
            _txn("2026-03-01", 3_500.00, "income"),  # Mar
            _txn("2026-03-10", -800.00, "housing"),  # Mar
        ]

    def test_start_date_excludes_earlier_transactions(self):
        result = calculate_budget_breakdown(self._mixed_date_txns(), start_date=date(2026, 3, 1))
        assert result["income"] == pytest.approx(3_500.0)

    def test_end_date_excludes_later_transactions(self):
        result = calculate_budget_breakdown(self._mixed_date_txns(), end_date=date(2026, 2, 28))
        assert result["income"] == pytest.approx(3_500.0)

    def test_both_dates_narrow_to_range(self):
        result = calculate_budget_breakdown(
            self._mixed_date_txns(), start_date=date(2026, 3, 1), end_date=date(2026, 3, 31)
        )
        assert result["income"] == pytest.approx(3_500.0)
        assert result["total_expenses"] == pytest.approx(800.0)

    def test_start_date_is_inclusive(self):
        txns = [_txn("2026-03-01", 3_500.00, "income")]
        result = calculate_budget_breakdown(txns, start_date=date(2026, 3, 1))
        assert result["income"] == pytest.approx(3_500.0)

    def test_end_date_is_inclusive(self):
        txns = [_txn("2026-03-31", 3_500.00, "income")]
        result = calculate_budget_breakdown(txns, end_date=date(2026, 3, 31))
        assert result["income"] == pytest.approx(3_500.0)

    def test_date_range_that_excludes_all_returns_zeros(self):
        result = calculate_budget_breakdown(
            STANDARD_TRANSACTIONS,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
        assert result["income"] == 0.0
        assert result["total_expenses"] == 0.0


class TestUnknownModel:
    def test_unknown_model_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown budget model"):
            calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="nonexistent")
