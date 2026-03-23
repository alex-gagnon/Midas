"""Integration tests for budget calculator against the sample CSV data."""

from datetime import date

import pytest

from src.calculators.budget import calculate_budget_breakdown


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

    @pytest.mark.parametrize(
        "model_key", ["50_30_20", "70_20_10", "80_20", "zero_based", "60_20_20", "kakeibo"]
    )
    def test_all_models_run_without_error(self, sample_transactions, model_key):
        result = calculate_budget_breakdown(
            sample_transactions, self.MARCH_START, self.MARCH_END, model_key=model_key
        )
        assert result["income"] > 0


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
        result = calculate_budget_breakdown(
            sample_transactions, date(2026, 3, 1), date(2026, 3, 31)
        )
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
