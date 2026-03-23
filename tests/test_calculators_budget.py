"""Unit tests for src/calculators/budget.py."""

from datetime import date

import pytest

from src.calculators.budget import calculate_budget_breakdown, list_budget_models
from src.calculators.budget_models import MODELS
from src.models.transaction import Transaction


def _txn(d, amount, category, account_id="chk_001", description=""):
    return Transaction(
        date=date.fromisoformat(d),
        amount=amount,
        description=description or category,
        category=category,
        account_id=account_id,
    )


# Standard fixture for most tests: 7000 income, clear expenses
STANDARD_TRANSACTIONS = [
    _txn("2026-03-01", 3_500.00, "income"),
    _txn("2026-03-15", 3_500.00, "income"),
    _txn("2026-03-01", -1_800.00, "housing"),
    _txn("2026-03-03", -200.00, "groceries"),
    _txn("2026-03-07", -100.00, "dining"),
    _txn("2026-03-10", -50.00, "shopping"),
    _txn("2026-03-14", -500.00, "retirement"),
    _txn("2026-03-15", -200.00, "savings"),
]
# income=7000, needs=1800+200=2000(housing+groceries), wants=100+50=150(dining+shopping),
# savings=500+200=700(retirement+savings)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Income calculation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Expense filtering
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------


class TestDateFiltering:
    def _mixed_date_txns(self):
        return [
            _txn("2026-02-01", 3_500.00, "income"),  # Feb
            _txn("2026-02-10", -500.00, "housing"),  # Feb
            _txn("2026-03-01", 3_500.00, "income"),  # Mar
            _txn("2026-03-10", -800.00, "housing"),  # Mar
        ]

    def test_start_date_excludes_earlier_transactions(self):
        txns = self._mixed_date_txns()
        result = calculate_budget_breakdown(txns, start_date=date(2026, 3, 1))
        assert result["income"] == pytest.approx(3_500.0)

    def test_end_date_excludes_later_transactions(self):
        txns = self._mixed_date_txns()
        result = calculate_budget_breakdown(txns, end_date=date(2026, 2, 28))
        assert result["income"] == pytest.approx(3_500.0)

    def test_both_dates_narrow_to_range(self):
        txns = self._mixed_date_txns()
        result = calculate_budget_breakdown(
            txns, start_date=date(2026, 3, 1), end_date=date(2026, 3, 31)
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


# ---------------------------------------------------------------------------
# Unknown model
# ---------------------------------------------------------------------------


class TestUnknownModel:
    def test_unknown_model_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown budget model"):
            calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="nonexistent")


# ---------------------------------------------------------------------------
# 50/30/20 model
# ---------------------------------------------------------------------------


class TestModel50_30_20:
    def test_bucket_names_present(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        assert set(result["breakdown"].keys()) == {"needs", "wants", "savings"}

    def test_housing_in_needs(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -400.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(400.0)

    def test_dining_in_wants(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-07", -100.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(100.0)

    def test_savings_in_savings_bucket(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-15", -200.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(200.0)

    def test_on_track_savings_when_meeting_20pct(self):
        # income=1000, savings=200 → 20%, target=20% gte → on_track=True
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["on_track"] is True

    def test_off_track_savings_when_below_20pct(self):
        # income=1000, savings=100 → 10%, target=20% gte → on_track=False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -100.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["on_track"] is False

    def test_on_track_needs_when_below_50pct(self):
        # income=1000, housing=300 → 30%, target=50% lte → on_track=True
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -300.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["on_track"] is True

    def test_off_track_needs_when_above_50pct(self):
        # income=1000, housing=600 → 60%, target=50% lte → on_track=False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -600.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["on_track"] is False

    def test_uncategorized_falls_into_default_bucket(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -100.00, "unknown_category"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        # default_bucket for 50_30_20 is "wants"
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(100.0)

    def test_category_matching_is_case_insensitive(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -300.00, "Housing"),  # capitalized
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(300.0)

    def test_remaining_is_income_minus_expenses(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -300.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["remaining"] == pytest.approx(600.0)

    def test_target_pct_values(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        assert result["breakdown"]["needs"]["target_pct"] == 50
        assert result["breakdown"]["wants"]["target_pct"] == 30
        assert result["breakdown"]["savings"]["target_pct"] == 20

    def test_actual_pct_calculation(self):
        # income=2000, housing=1000 → 50.0%
        txns = [
            _txn("2026-03-01", 2_000.00, "income"),
            _txn("2026-03-01", -1_000.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["actual_pct"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 70/20/10 model
# ---------------------------------------------------------------------------


class TestModel70_20_10:
    def test_bucket_names_present(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="70_20_10")
        assert set(result["breakdown"].keys()) == {"living", "savings", "giving_debt"}

    def test_housing_and_dining_both_in_living(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -400.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="70_20_10")
        assert result["breakdown"]["living"]["amount"] == pytest.approx(500.0)

    def test_gifts_in_giving_debt_bucket(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -50.00, "gifts"),
        ]
        result = calculate_budget_breakdown(txns, model_key="70_20_10")
        assert result["breakdown"]["giving_debt"]["amount"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 80/20 model
# ---------------------------------------------------------------------------


class TestModel80_20:
    def test_bucket_names_present(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="80_20")
        assert set(result["breakdown"].keys()) == {"savings", "spending"}

    def test_on_track_savings_at_exactly_20pct(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="80_20")
        assert result["breakdown"]["savings"]["on_track"] is True


# ---------------------------------------------------------------------------
# Zero-based model
# ---------------------------------------------------------------------------


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
        categories = {li["category"] for li in result["line_items"]}
        assert categories == {"housing", "dining"}

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
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -999.50, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert result["on_track"] is True

    def test_off_track_when_remaining_exceeds_one_dollar(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -500.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        assert result["on_track"] is False

    def test_income_category_excluded_from_line_items(self):
        txns = [_txn("2026-03-01", 3_000.00, "income")]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        categories = [li["category"] for li in result["line_items"]]
        assert "income" not in categories

    def test_positive_non_income_amounts_excluded(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-10", 50.00, "refund"),  # positive non-income → skip
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        categories = [li["category"] for li in result["line_items"]]
        assert "refund" not in categories

    def test_line_item_pct_of_income(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -250.00, "housing"),
        ]
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


# ---------------------------------------------------------------------------
# Zero-based: over_budget flag
# ---------------------------------------------------------------------------


class TestZeroBasedOverBudgetFlag:
    """Tests for the over_budget bool on zero_based line items (True when > 15% of income)."""

    def test_exactly_15_pct_is_not_over_budget(self):
        # income=1000, category spend=150 → 15.0% → over_budget should be False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -150.00, "groceries"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "groceries")
        assert item["over_budget"] is False

    def test_above_15_pct_is_over_budget(self):
        # income=1000, category spend=160 → 16.0% → over_budget should be True
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -160.00, "groceries"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "groceries")
        assert item["over_budget"] is True

    def test_well_below_15_pct_is_not_over_budget(self):
        # income=1000, category spend=50 → 5.0% → over_budget should be False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -50.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "dining")
        assert item["over_budget"] is False

    def test_multiple_categories_independent_over_budget_flags(self):
        # income=1000
        # housing=200 → 20% → over_budget=True
        # dining=50  →  5% → over_budget=False
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
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = result["line_items"][0]
        assert isinstance(item["over_budget"], bool)

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
            (151.00, True),  # 15.1% → over (first value that unambiguously rounds above 15.0)
            (200.00, True),  # 20.0% → over
        ],
    )
    def test_boundary_parametrized(self, spend, expected):
        """Boundary cases around the 15% threshold with income=1000.

        Note: pct_of_income is rounded to 1 decimal place before the > 15.0
        comparison, so the effective threshold is anything that rounds to > 15.0.
        Due to Python's banker's rounding, 150.5 (15.05%) rounds to 15.0 (ties
        round to even), so the first unambiguously over-budget value is 151.0 (15.1%).
        """
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -spend, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="zero_based")
        item = next(li for li in result["line_items"] if li["category"] == "housing")
        assert item["over_budget"] is expected


# ---------------------------------------------------------------------------
# list_budget_models
# ---------------------------------------------------------------------------


class TestListBudgetModels:
    def test_returns_list(self):
        models = list_budget_models()
        assert isinstance(models, list)

    def test_all_six_models_present(self):
        models = list_budget_models()
        keys = {m["key"] for m in models}
        assert keys == {"50_30_20", "70_20_10", "80_20", "zero_based", "60_20_20", "kakeibo"}

    def test_each_model_has_required_fields(self):
        for m in list_budget_models():
            assert "key" in m
            assert "name" in m
            assert "description" in m

    def test_matches_models_registry(self):
        listed = {m["key"] for m in list_budget_models()}
        assert listed == set(MODELS.keys())


# ---------------------------------------------------------------------------
# Integration: sample data
# ---------------------------------------------------------------------------


class TestBudgetWithSampleData:
    """Integration tests against sample data scoped to March 2026."""

    MARCH_START = date(2026, 3, 1)
    MARCH_END = date(2026, 3, 31)

    def test_income_from_sample_is_7000(self, sample_transactions):
        result = calculate_budget_breakdown(sample_transactions, self.MARCH_START, self.MARCH_END)
        assert result["income"] == pytest.approx(7_000.0)

    def test_all_buckets_have_non_negative_amounts(self, sample_transactions):
        result = calculate_budget_breakdown(sample_transactions, self.MARCH_START, self.MARCH_END)
        for bucket_name, bucket in result["breakdown"].items():
            assert bucket["amount"] >= 0, f"Bucket '{bucket_name}' has negative amount"

    def test_actual_pct_sums_to_total_expense_pct(self, sample_transactions):
        result = calculate_budget_breakdown(sample_transactions, self.MARCH_START, self.MARCH_END)
        total_expense_pct = round(result["total_expenses"] / result["income"] * 100, 1)
        bucket_pct_sum = round(sum(b["actual_pct"] for b in result["breakdown"].values()), 1)
        assert bucket_pct_sum == pytest.approx(total_expense_pct, abs=0.2)  # rounding tolerance

    @pytest.mark.parametrize("model_key", ["50_30_20", "70_20_10", "80_20", "zero_based", "60_20_20", "kakeibo"])
    def test_all_models_run_without_error(self, sample_transactions, model_key):
        result = calculate_budget_breakdown(sample_transactions, self.MARCH_START, self.MARCH_END, model_key=model_key)
        assert result["income"] > 0


# ---------------------------------------------------------------------------
# Multi-month filtering: the cross-period discrepancy scenario
# ---------------------------------------------------------------------------


class TestBudgetMultiMonthFiltering:
    """
    Verify that date filtering correctly isolates a single period when the
    data spans multiple months. The sample data covers Jan–Mar 2026 (3 × $7k
    income = $21k total), so without a date range the calculator aggregates
    all three months — producing the inflated outgoing the user observed.
    """

    def test_all_three_months_income_without_filter(self, sample_transactions):
        result = calculate_budget_breakdown(sample_transactions)
        assert result["income"] == pytest.approx(21_000.0)

    def test_march_filter_returns_only_march_income(self, sample_transactions):
        result = calculate_budget_breakdown(sample_transactions, date(2026, 3, 1), date(2026, 3, 31))
        assert result["income"] == pytest.approx(7_000.0)

    def test_march_expenses_lower_than_unfiltered(self, sample_transactions):
        march = calculate_budget_breakdown(sample_transactions, date(2026, 3, 1), date(2026, 3, 31))
        all_time = calculate_budget_breakdown(sample_transactions)
        assert march["total_expenses"] < all_time["total_expenses"]

    def test_cross_period_discrepancy_scenario(self, sample_transactions):
        """
        Reproduce the original bug: a dataset where income only appears in one
        month but expenses span multiple months. Without a date filter the
        expense/income ratio is wildly inflated; with a date filter it is sane.
        """
        # Keep all expenses but only March income (as if earlier paychecks
        # were recorded in a different system and not imported yet).
        partial = [t for t in sample_transactions if t.category != "income" or t.date.month == 3]

        unbounded = calculate_budget_breakdown(partial)
        march_only = calculate_budget_breakdown(partial, date(2026, 3, 1), date(2026, 3, 31))

        # Income is the same either way (only March paychecks exist).
        assert unbounded["income"] == pytest.approx(march_only["income"])

        # But expenses are much higher in the unbounded result because Jan/Feb
        # costs are included even though their income is missing.
        assert unbounded["total_expenses"] > march_only["total_expenses"]

        # The unbounded call produces an expense ratio > 100 % — the discrepancy.
        assert unbounded["total_expenses"] / unbounded["income"] > 1.0
        assert march_only["total_expenses"] / march_only["income"] < 1.0

    def test_each_month_balanced_individually(self, sample_transactions):
        for month, start, end in [
            ("January", date(2026, 1, 1), date(2026, 1, 31)),
            ("February", date(2026, 2, 1), date(2026, 2, 28)),
            ("March", date(2026, 3, 1), date(2026, 3, 31)),
        ]:
            result = calculate_budget_breakdown(sample_transactions, start, end)
            assert result["income"] == pytest.approx(7_000.0), f"{month} income wrong"
            assert result["total_expenses"] < result["income"], f"{month} is overspent"


# ---------------------------------------------------------------------------
# Model registration: new models
# ---------------------------------------------------------------------------


class TestModelRegistration:
    def test_60_20_20_registered_in_models(self):
        assert "60_20_20" in MODELS

    def test_kakeibo_registered_in_models(self):
        assert "kakeibo" in MODELS

    def test_60_20_20_model_key_matches_registry_key(self):
        assert MODELS["60_20_20"].key == "60_20_20"

    def test_kakeibo_model_key_matches_registry_key(self):
        assert MODELS["kakeibo"].key == "kakeibo"


# ---------------------------------------------------------------------------
# 60/20/20 model — structure
# ---------------------------------------------------------------------------


class TestModel60_20_20Structure:
    def test_bucket_names_are_needs_wants_savings(self):
        model = MODELS["60_20_20"]
        names = {b.name for b in model.buckets}
        assert names == {"needs", "wants", "savings"}

    def test_needs_target_pct_is_60(self):
        model = MODELS["60_20_20"]
        needs = next(b for b in model.buckets if b.name == "needs")
        assert needs.target_pct == 60

    def test_wants_target_pct_is_20(self):
        model = MODELS["60_20_20"]
        wants = next(b for b in model.buckets if b.name == "wants")
        assert wants.target_pct == 20

    def test_savings_target_pct_is_20(self):
        model = MODELS["60_20_20"]
        savings = next(b for b in model.buckets if b.name == "savings")
        assert savings.target_pct == 20

    def test_needs_on_track_direction_is_lte(self):
        model = MODELS["60_20_20"]
        needs = next(b for b in model.buckets if b.name == "needs")
        assert needs.on_track_direction == "lte"

    def test_wants_on_track_direction_is_lte(self):
        model = MODELS["60_20_20"]
        wants = next(b for b in model.buckets if b.name == "wants")
        assert wants.on_track_direction == "lte"

    def test_savings_on_track_direction_is_gte(self):
        model = MODELS["60_20_20"]
        savings = next(b for b in model.buckets if b.name == "savings")
        assert savings.on_track_direction == "gte"


# ---------------------------------------------------------------------------
# 60/20/20 model — calculator behaviour
# ---------------------------------------------------------------------------


class TestModel60_20_20:
    def test_bucket_names_present_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="60_20_20")
        assert set(result["breakdown"].keys()) == {"needs", "wants", "savings"}

    def test_housing_classified_in_needs(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -500.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(500.0)

    def test_dining_classified_in_wants(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -150.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(150.0)

    def test_retirement_classified_in_savings(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "retirement"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(200.0)

    def test_target_pct_values_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="60_20_20")
        assert result["breakdown"]["needs"]["target_pct"] == 60
        assert result["breakdown"]["wants"]["target_pct"] == 20
        assert result["breakdown"]["savings"]["target_pct"] == 20

    def test_on_track_needs_when_at_exactly_60pct(self):
        # income=1000, housing=600 → 60.0% → lte 60 → on_track=True
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -600.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is True

    def test_off_track_needs_when_above_60pct(self):
        # income=1000, housing=700 → 70.0% → lte 60 → on_track=False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -700.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is False

    def test_on_track_savings_when_meeting_20pct(self):
        # income=1000, savings=200 → 20% → gte 20 → on_track=True
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["on_track"] is True

    def test_off_track_savings_when_below_20pct(self):
        # income=1000, savings=100 → 10% → gte 20 → on_track=False
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -100.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["on_track"] is False

    def test_uncategorized_falls_into_wants(self):
        # default_bucket for 60_20_20 is "wants"
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -75.00, "unknown_category"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(75.0)

    def test_actual_pct_calculation(self):
        # income=2000, savings=600 → 30.0%
        txns = [
            _txn("2026-03-01", 2_000.00, "income"),
            _txn("2026-03-01", -600.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["actual_pct"] == pytest.approx(30.0)

    def test_remaining_is_income_minus_expenses(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -600.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["remaining"] == pytest.approx(300.0)

    def test_category_matching_is_case_insensitive(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -400.00, "HOUSING"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(400.0)

    @pytest.mark.parametrize(
        "needs_spend,expected_on_track",
        [
            (550.0, True),   # 55% < 60% → on_track
            (600.0, True),   # exactly 60% → on_track (lte is inclusive)
            (601.0, False),  # 60.1% > 60% → off_track
        ],
    )
    def test_needs_boundary_parametrized(self, needs_spend, expected_on_track):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -needs_spend, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is expected_on_track


# ---------------------------------------------------------------------------
# Kakeibo model — structure
# ---------------------------------------------------------------------------


class TestModelKakeiboStructure:
    def test_has_five_buckets(self):
        model = MODELS["kakeibo"]
        assert len(model.buckets) == 5

    def test_bucket_names_are_correct(self):
        model = MODELS["kakeibo"]
        names = {b.name for b in model.buckets}
        assert names == {"survival", "optional", "culture", "extra", "savings"}

    def test_savings_bucket_on_track_direction_is_gte(self):
        model = MODELS["kakeibo"]
        savings = next(b for b in model.buckets if b.name == "savings")
        assert savings.on_track_direction == "gte"

    def test_non_savings_buckets_have_no_on_track_direction(self):
        model = MODELS["kakeibo"]
        non_savings = [b for b in model.buckets if b.name != "savings"]
        for bucket in non_savings:
            assert bucket.on_track_direction is None, (
                f"Bucket '{bucket.name}' should have on_track_direction=None"
            )

    def test_all_buckets_have_no_target_pct(self):
        # Kakeibo is purely informational — no numeric targets on any bucket
        model = MODELS["kakeibo"]
        for bucket in model.buckets:
            assert bucket.target_pct is None, (
                f"Bucket '{bucket.name}' should have target_pct=None"
            )

    def test_default_bucket_is_extra(self):
        model = MODELS["kakeibo"]
        assert model.default_bucket == "extra"


# ---------------------------------------------------------------------------
# Kakeibo model — calculator behaviour
# ---------------------------------------------------------------------------


class TestModelKakeibo:
    def test_bucket_names_present_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert set(result["breakdown"].keys()) == {
            "survival", "optional", "culture", "extra", "savings"
        }

    def test_housing_classified_in_survival(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -800.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["survival"]["amount"] == pytest.approx(800.0)

    def test_dining_classified_in_optional(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -120.00, "dining"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["optional"]["amount"] == pytest.approx(120.0)

    def test_education_classified_in_culture(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -80.00, "education"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["culture"]["amount"] == pytest.approx(80.0)

    def test_gifts_classified_in_culture(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -50.00, "gifts"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["culture"]["amount"] == pytest.approx(50.0)

    def test_debt_payment_classified_in_extra(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "debt_payment"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["extra"]["amount"] == pytest.approx(200.0)

    def test_savings_classified_in_savings(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -150.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(150.0)

    def test_retirement_classified_in_savings(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -300.00, "retirement"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(300.0)

    def test_uncategorized_falls_into_extra(self):
        # default_bucket for kakeibo is "extra"
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -60.00, "mystery_expense"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["extra"]["amount"] == pytest.approx(60.0)

    def test_non_savings_buckets_have_no_on_track_key(self):
        # target_pct=None on these buckets means the calculator omits "on_track"
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -400.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
            _txn("2026-03-01", -50.00, "education"),
            _txn("2026-03-01", -50.00, "debt_payment"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        for bucket_name in ("survival", "optional", "culture", "extra"):
            assert "on_track" not in result["breakdown"][bucket_name], (
                f"Bucket '{bucket_name}' should not have an on_track key "
                "(target_pct is None, so no on_track assessment is possible)"
            )

    def test_savings_bucket_has_no_on_track_key_due_to_null_target_pct(self):
        # savings has on_track_direction="gte" but target_pct=None.
        # The calculator guards: if bucket.on_track_direction AND bucket.target_pct is not None.
        # Since target_pct IS None, "on_track" is NOT emitted — this is intentional kakeibo
        # behaviour (savings is aspirational/informational, not a hard numeric target).
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -200.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert "on_track" not in result["breakdown"]["savings"]

    def test_target_pct_is_none_for_all_buckets_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        for bucket_name, bucket in result["breakdown"].items():
            assert bucket["target_pct"] is None, (
                f"Bucket '{bucket_name}' should have target_pct=None in result"
            )

    def test_actual_pct_calculated_correctly(self):
        # income=1000, housing=500 → 50.0%
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -500.00, "housing"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["survival"]["actual_pct"] == pytest.approx(50.0)

    def test_remaining_is_income_minus_expenses(self):
        txns = [
            _txn("2026-03-01", 1_000.00, "income"),
            _txn("2026-03-01", -600.00, "housing"),
            _txn("2026-03-01", -100.00, "dining"),
            _txn("2026-03-01", -50.00, "savings"),
        ]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["remaining"] == pytest.approx(250.0)

    def test_standard_transactions_income_and_expense_totals(self):
        # STANDARD_TRANSACTIONS: income=7000, needs=2000, wants=150, savings=700
        # In kakeibo: housing+groceries → survival, dining+shopping → optional, retirement+savings → savings
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert result["income"] == pytest.approx(7_000.0)
        assert result["breakdown"]["survival"]["amount"] == pytest.approx(2_000.0)
        assert result["breakdown"]["optional"]["amount"] == pytest.approx(150.0)
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(700.0)

    def test_result_has_standard_top_level_keys(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert set(result.keys()) == {
            "model", "period", "income", "total_expenses", "remaining", "breakdown"
        }

    def test_model_info_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert result["model"]["key"] == "kakeibo"
        assert result["model"]["name"] == "Kakeibo"
