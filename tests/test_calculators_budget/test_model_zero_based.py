"""Tests for the zero-based budget model."""

import pytest

from src.calculators.budget import calculate_budget_breakdown

from ._shared import STANDARD_TRANSACTIONS, _txn


class TestModelZeroBased:
    def test_returns_line_items_not_breakdown(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="zero_based")
        assert "line_items" in result
        assert "breakdown" not in result

    def test_each_category_is_separate_line_item(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -300.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert {li["category"] for li in result["line_items"]} == {"housing", "dining"}

    def test_line_items_sorted_by_amount_descending(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -50.00, "dining"),
            _txn("2026-03-01", -400.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        amounts = [li["amount"] for li in result["line_items"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_on_track_when_remaining_within_one_dollar(self):
        # income=1000, expenses=999.50 → remaining=0.50 → on_track=True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -999.50, "housing")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert result["on_track"] is True

    def test_off_track_when_remaining_exceeds_one_dollar(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -500.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert result["on_track"] is False

    def test_income_category_excluded_from_line_items(self):
        txns = [_txn("2026-03-01", 3_000.00, "income")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert "income" not in [li["category"] for li in result["line_items"]]

    def test_positive_non_income_amounts_excluded(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-10", 50.00, "refund"),  # positive non-income → skip
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert "refund" not in [li["category"] for li in result["line_items"]]

    def test_line_item_pct_of_income(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -250.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        housing = next(li for li in result["line_items"] if li["category"] == "housing")
        assert housing["pct_of_income"] == pytest.approx(25.0)

    def test_same_category_multiple_transactions_aggregated(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-03", -100.00, "groceries"),
            _txn("2026-03-10", -50.00, "groceries"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        groceries = next(li for li in result["line_items"] if li["category"] == "groceries")
        assert groceries["amount"] == pytest.approx(150.0)


class TestZeroBasedOverBudgetFlag:
    """Tests for the over_budget bool on zero_based line items (True when > 15% of income)."""

    def test_exactly_15_pct_is_not_over_budget(self):
        # income=1000, category spend=150 → 15.0% → over_budget should be False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -150.00, "groceries")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "groceries")
        assert item["over_budget"] is False

    def test_above_15_pct_is_over_budget(self):
        # income=1000, category spend=160 → 16.0% → over_budget should be True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -160.00, "groceries")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "groceries")
        assert item["over_budget"] is True

    def test_well_below_15_pct_is_not_over_budget(self):
        # income=1000, category spend=50 → 5.0% → over_budget should be False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -50.00, "dining")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "dining")
        assert item["over_budget"] is False

    def test_multiple_categories_independent_over_budget_flags(self):
        # income=1000, housing=200 → 20% → over_budget=True, dining=50 → 5% → over_budget=False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "housing"),
            _txn("2026-03-01", -50.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        items = {li["category"]: li for li in result["line_items"]}
        assert items["housing"]["over_budget"] is True
        assert items["dining"]["over_budget"] is False

    def test_over_budget_key_present_on_every_line_item(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -100.00, "housing"),
            _txn("2026-03-01", -50.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        for item in result["line_items"]:
            assert "over_budget" in item, f"'over_budget' missing from {item}"

    def test_over_budget_is_bool_not_truthy_value(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert isinstance(result["line_items"][0]["over_budget"], bool)

    def test_over_budget_not_present_on_percentage_model_buckets(self):
        # over_budget is a zero_based-only feature; 50_30_20 buckets should NOT have it
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        for bucket in result["breakdown"].values():
            assert "over_budget" not in bucket

    @pytest.mark.parametrize(
        "spend,expected",
        [
            (149.99, False),  # 14.999% → rounds to 15.0% → not over
            (150.00, False),  # exactly 15.0% → not over
            (151.00, True),   # 15.1% → over (first value that unambiguously rounds above 15.0)
            (200.00, True),   # 20.0% → over
        ],
    )
    def test_boundary_parametrized(self, spend, expected):
        """Boundary cases around the 15% threshold with income=1000.

        Note: pct_of_income is rounded to 1 decimal place before the > 15.0
        comparison, so the effective threshold is anything that rounds to > 15.0.
        Due to Python's banker's rounding, 150.5 (15.05%) rounds to 15.0 (ties
        round to even), so the first unambiguously over-budget value is 151.0 (15.1%).
        """
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -spend, "housing")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "housing")
        assert item["over_budget"] is expected
