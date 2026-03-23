"""Tests for calculate_monthly_budget_breakdown."""

from datetime import date
from unittest.mock import patch

import pytest

from src.calculators.budget import calculate_monthly_budget_breakdown
from src.models.transaction import Transaction

THREE_MONTH_TRANSACTIONS = [
    # Jan 2026
    Transaction(
        date=date(2026, 1, 15),
        amount=7000.0,
        category="income",
        description="Salary",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 1, 20),
        amount=-2000.0,
        category="housing",
        description="Rent",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 1, 25),
        amount=-500.0,
        category="groceries",
        description="Groceries",
        account_id="chk_001",
    ),
    # Feb 2026
    Transaction(
        date=date(2026, 2, 15),
        amount=7000.0,
        category="income",
        description="Salary",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 2, 20),
        amount=-2000.0,
        category="housing",
        description="Rent",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 2, 25),
        amount=-600.0,
        category="groceries",
        description="Groceries",
        account_id="chk_001",
    ),
    # Mar 2026
    Transaction(
        date=date(2026, 3, 15),
        amount=7000.0,
        category="income",
        description="Salary",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 3, 20),
        amount=-2000.0,
        category="housing",
        description="Rent",
        account_id="chk_001",
    ),
    Transaction(
        date=date(2026, 3, 25),
        amount=-700.0,
        category="groceries",
        description="Groceries",
        account_id="chk_001",
    ),
]


class TestMonthlyBudgetBreakdown:
    def test_single_month_returns_one_entry(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        assert result["months_count"] == 1
        assert len(result["months"]) == 1

    def test_three_months_returns_three_entries(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        assert result["months_count"] == 3
        assert len(result["months"]) == 3

    def test_month_labels_correct_format(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        for entry in result["months"]:
            assert "month" in entry
            year_part, month_part = entry["month"].split("-")
            assert len(year_part) == 4 and year_part.isdigit()
            assert len(month_part) == 2 and month_part.isdigit()

    def test_month_labels_chronological(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        labels = [entry["month"] for entry in result["months"]]
        assert labels == sorted(labels)

    def test_each_entry_has_breakdown_structure(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        for entry in result["months"]:
            assert "income" in entry
            assert "total_expenses" in entry
            assert "remaining" in entry
            assert "breakdown" in entry

    def test_income_scoped_to_month(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        jan_entry = next(e for e in result["months"] if e["month"] == "2026-01")
        assert jan_entry["income"] == pytest.approx(7000.0)

    def test_expenses_scoped_to_month(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        jan_entry = next(e for e in result["months"] if e["month"] == "2026-01")
        assert jan_entry["total_expenses"] == pytest.approx(2500.0)

    def test_empty_month_produces_zeros(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        apr_entry = result["months"][0]
        assert apr_entry["income"] == 0.0
        assert apr_entry["total_expenses"] == 0.0

    def test_model_at_top_level(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        assert "model" in result
        assert result["model"]["key"] == "50_30_20"
        for entry in result["months"]:
            assert "model" not in entry

    def test_zero_based_produces_line_items_per_month(self):
        result = calculate_monthly_budget_breakdown(
            THREE_MONTH_TRANSACTIONS,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            model_key="zero_based",
        )
        assert result["model"]["key"] == "zero_based"
        for entry in result["months"]:
            assert "line_items" in entry

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            calculate_monthly_budget_breakdown(
                THREE_MONTH_TRANSACTIONS,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 1, 31),
            )

    def test_default_none_dates_returns_current_month(self):
        fixed_today = date(2026, 3, 15)
        with patch("src.calculators.budget.date") as mock_date_cls:
            mock_date_cls.side_effect = date
            mock_date_cls.today.return_value = fixed_today
            result = calculate_monthly_budget_breakdown(THREE_MONTH_TRANSACTIONS)
        assert result["months_count"] == 1
        assert result["months"][0]["month"] == "2026-03"
