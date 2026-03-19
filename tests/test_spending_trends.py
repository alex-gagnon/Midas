"""Unit tests for src/calculators/spending_trends.py."""

from datetime import date

import pytest

from src.calculators.spending_trends import calculate_spending_trends
from src.models.transaction import Transaction


def _txn(d: str, amount: float, category: str, account_id: str = "chk_001") -> Transaction:
    return Transaction(
        date=date.fromisoformat(d),
        amount=amount,
        description=category,
        category=category,
        account_id=account_id,
    )


# Six months of expense data across different months.
# Months: 2025-10, 2025-11, 2025-12, 2026-01, 2026-02, 2026-03
SIX_MONTH_TRANSACTIONS = [
    _txn("2025-10-05", -300.00, "housing"),
    _txn("2025-10-10", -50.00, "dining"),
    _txn("2025-11-05", -310.00, "housing"),
    _txn("2025-11-12", -60.00, "dining"),
    _txn("2025-12-05", -320.00, "housing"),
    _txn("2025-12-15", -70.00, "dining"),
    _txn("2026-01-05", -330.00, "housing"),
    _txn("2026-01-18", -80.00, "dining"),
    _txn("2026-02-05", -340.00, "housing"),
    _txn("2026-02-20", -90.00, "dining"),
    _txn("2026-03-05", -350.00, "housing"),
    _txn("2026-03-22", -100.00, "dining"),
    # Income and savings — must be excluded from spend
    _txn("2026-03-01", 3_500.00, "income"),
    _txn("2026-03-15", -200.00, "savings"),
    _txn("2026-03-14", -500.00, "retirement"),
]


class TestSpendingTrendsShape:
    def test_returns_expected_top_level_keys(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        assert set(result.keys()) == {"months_shown", "trend"}

    def test_trend_is_list(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        assert isinstance(result["trend"], list)

    def test_each_trend_entry_has_required_keys(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        for entry in result["trend"]:
            assert set(entry.keys()) == {"month", "total_spent", "top_categories"}

    def test_month_format_is_yyyy_mm(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        for entry in result["trend"]:
            parts = entry["month"].split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4  # year
            assert len(parts[1]) == 2  # zero-padded month

    def test_trend_is_in_chronological_order(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        months = [entry["month"] for entry in result["trend"]]
        assert months == sorted(months)


class TestSpendingTrendsMonthCount:
    def test_default_months_6_returns_up_to_6(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS)
        assert result["months_shown"] == 6
        assert len(result["trend"]) == 6

    def test_months_1_returns_exactly_1_most_recent(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS, months=1)
        assert result["months_shown"] == 1
        assert len(result["trend"]) == 1
        assert result["trend"][0]["month"] == "2026-03"

    def test_months_3_returns_3_most_recent(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS, months=3)
        assert result["months_shown"] == 3
        months = [e["month"] for e in result["trend"]]
        assert months == ["2026-01", "2026-02", "2026-03"]

    def test_months_larger_than_available_returns_all(self):
        txns = [_txn("2026-03-01", -100.00, "dining")]
        result = calculate_spending_trends(txns, months=6)
        assert result["months_shown"] == 1

    def test_months_shown_equals_trend_length(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS, months=4)
        assert result["months_shown"] == len(result["trend"])


class TestSpendingTrendsExclusions:
    def test_income_category_excluded_from_spend(self):
        txns = [
            _txn("2026-03-01", 3_500.00, "income"),
            _txn("2026-03-05", -300.00, "housing"),
        ]
        result = calculate_spending_trends(txns)
        assert result["months_shown"] == 1
        cats = [c["category"] for c in result["trend"][0]["top_categories"]]
        assert "income" not in cats

    def test_savings_category_excluded_from_spend(self):
        txns = [
            _txn("2026-03-05", -300.00, "housing"),
            _txn("2026-03-15", -200.00, "savings"),
        ]
        result = calculate_spending_trends(txns)
        cats = [c["category"] for c in result["trend"][0]["top_categories"]]
        assert "savings" not in cats

    def test_retirement_category_excluded_from_spend(self):
        txns = [
            _txn("2026-03-05", -300.00, "housing"),
            _txn("2026-03-14", -500.00, "retirement"),
        ]
        result = calculate_spending_trends(txns)
        cats = [c["category"] for c in result["trend"][0]["top_categories"]]
        assert "retirement" not in cats

    def test_positive_non_income_amounts_excluded(self):
        txns = [
            _txn("2026-03-05", -300.00, "housing"),
            _txn("2026-03-10", 50.00, "refund"),
        ]
        result = calculate_spending_trends(txns)
        cats = [c["category"] for c in result["trend"][0]["top_categories"]]
        assert "refund" not in cats

    def test_total_spent_excludes_savings_and_retirement(self):
        txns = [
            _txn("2026-03-05", -300.00, "housing"),
            _txn("2026-03-14", -500.00, "retirement"),
            _txn("2026-03-15", -200.00, "savings"),
        ]
        result = calculate_spending_trends(txns)
        assert result["trend"][0]["total_spent"] == pytest.approx(300.0)

    def test_income_transactions_do_not_inflate_total_spent(self):
        txns = [
            _txn("2026-03-01", 3_500.00, "income"),
            _txn("2026-03-05", -100.00, "dining"),
        ]
        result = calculate_spending_trends(txns)
        assert result["trend"][0]["total_spent"] == pytest.approx(100.0)


class TestSpendingTrendsTopCategories:
    def test_top_categories_capped_at_5(self):
        txns = [
            _txn("2026-03-01", -100.00, "housing"),
            _txn("2026-03-02", -90.00, "dining"),
            _txn("2026-03-03", -80.00, "groceries"),
            _txn("2026-03-04", -70.00, "transport"),
            _txn("2026-03-05", -60.00, "fitness"),
            _txn("2026-03-06", -50.00, "shopping"),
            _txn("2026-03-07", -40.00, "utilities"),
        ]
        result = calculate_spending_trends(txns)
        assert len(result["trend"][0]["top_categories"]) <= 5

    def test_top_categories_sorted_by_amount_descending(self):
        txns = [
            _txn("2026-03-01", -50.00, "dining"),
            _txn("2026-03-02", -300.00, "housing"),
            _txn("2026-03-03", -100.00, "groceries"),
        ]
        result = calculate_spending_trends(txns)
        amounts = [c["amount"] for c in result["trend"][0]["top_categories"]]
        assert amounts == sorted(amounts, reverse=True)

    def test_top_categories_highest_spend_wins_when_capped(self):
        txns = [
            _txn("2026-03-01", -100.00, "housing"),
            _txn("2026-03-02", -90.00, "dining"),
            _txn("2026-03-03", -80.00, "groceries"),
            _txn("2026-03-04", -70.00, "transport"),
            _txn("2026-03-05", -60.00, "fitness"),
            _txn("2026-03-06", -50.00, "shopping"),
            _txn("2026-03-07", -40.00, "utilities"),
        ]
        result = calculate_spending_trends(txns)
        cats = {c["category"] for c in result["trend"][0]["top_categories"]}
        assert "shopping" not in cats
        assert "utilities" not in cats
        assert "housing" in cats

    def test_top_categories_each_have_category_and_amount(self):
        txns = [_txn("2026-03-01", -100.00, "dining")]
        result = calculate_spending_trends(txns)
        for cat in result["trend"][0]["top_categories"]:
            assert "category" in cat
            assert "amount" in cat

    def test_amounts_are_rounded_to_two_decimal_places(self):
        txns = [_txn("2026-03-01", -333.333, "dining")]
        result = calculate_spending_trends(txns)
        amt = result["trend"][0]["top_categories"][0]["amount"]
        assert amt == round(amt, 2)

    def test_multiple_transactions_same_category_aggregated(self):
        txns = [
            _txn("2026-03-01", -100.00, "dining"),
            _txn("2026-03-10", -50.00, "dining"),
        ]
        result = calculate_spending_trends(txns)
        dining = next(c for c in result["trend"][0]["top_categories"] if c["category"] == "dining")
        assert dining["amount"] == pytest.approx(150.0)


class TestSpendingTrendsEmpty:
    def test_empty_transactions_months_shown_is_zero(self):
        result = calculate_spending_trends([])
        assert result["months_shown"] == 0

    def test_empty_transactions_trend_is_empty_list(self):
        result = calculate_spending_trends([])
        assert result["trend"] == []

    def test_only_income_transactions_months_shown_is_zero(self):
        txns = [
            _txn("2026-03-01", 3_500.00, "income"),
            _txn("2026-03-15", 3_500.00, "income"),
        ]
        result = calculate_spending_trends(txns)
        assert result["months_shown"] == 0
        assert result["trend"] == []

    def test_only_savings_and_retirement_months_shown_is_zero(self):
        txns = [
            _txn("2026-03-14", -500.00, "retirement"),
            _txn("2026-03-15", -200.00, "savings"),
        ]
        result = calculate_spending_trends(txns)
        assert result["months_shown"] == 0

    def test_months_0_returns_empty(self):
        result = calculate_spending_trends(SIX_MONTH_TRANSACTIONS, months=0)
        assert result["months_shown"] == 0
        assert result["trend"] == []


class TestSpendingTrendsTotalSpent:
    def test_total_spent_is_sum_of_absolute_expense_amounts(self):
        txns = [
            _txn("2026-03-01", -300.00, "housing"),
            _txn("2026-03-07", -100.00, "dining"),
        ]
        result = calculate_spending_trends(txns)
        assert result["trend"][0]["total_spent"] == pytest.approx(400.0)

    def test_total_spent_is_rounded_to_two_decimal_places(self):
        txns = [_txn("2026-03-01", -333.333, "dining")]
        result = calculate_spending_trends(txns)
        val = result["trend"][0]["total_spent"]
        assert val == round(val, 2)


class TestSpendingTrendsWithSampleData:
    def test_sample_data_has_one_month(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_spending_trends(txns)
        assert result["months_shown"] == 1
        assert result["trend"][0]["month"] == "2026-03"

    def test_sample_data_months_1_returns_march(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_spending_trends(txns, months=1)
        assert result["months_shown"] == 1
        assert result["trend"][0]["month"] == "2026-03"

    def test_sample_data_savings_excluded_from_total(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_spending_trends(txns)
        cats = [c["category"] for c in result["trend"][0]["top_categories"]]
        assert "savings" not in cats
        assert "retirement" not in cats

    def test_sample_data_top_categories_capped_at_5(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_spending_trends(txns)
        assert len(result["trend"][0]["top_categories"]) <= 5

    def test_sample_data_total_spent_is_positive(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_spending_trends(txns)
        assert result["trend"][0]["total_spent"] > 0
