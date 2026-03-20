"""Unit tests for src/calculators/savings_rate.py."""

from datetime import date

import pytest

from src.calculators.savings_rate import calculate_savings_rate
from src.models.transaction import Transaction


def _txn(d: str, amount: float, category: str, account_id: str = "chk_001") -> Transaction:
    return Transaction(
        date=date.fromisoformat(d),
        amount=amount,
        description=category,
        category=category,
        account_id=account_id,
    )


# Standard fixture: income=7000, savings=200, retirement=500 → total_saved=700, rate=10.0
STANDARD_TRANSACTIONS = [
    _txn("2026-03-01", 3_500.00, "income"),
    _txn("2026-03-15", 3_500.00, "income"),
    _txn("2026-03-01", -1_800.00, "housing"),
    _txn("2026-03-03", -200.00, "groceries"),
    _txn("2026-03-07", -100.00, "dining"),
    _txn("2026-03-14", -500.00, "retirement"),
    _txn("2026-03-15", -200.00, "savings"),
]


class TestSavingsRateShape:
    def test_returns_expected_top_level_keys(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert set(result.keys()) == {
            "period",
            "income",
            "total_saved",
            "savings_rate_pct",
            "breakdown",
        }

    def test_period_is_none_when_no_dates_provided(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["period"]["start"] is None
        assert result["period"]["end"] is None

    def test_period_reflects_provided_dates(self):
        result = calculate_savings_rate(
            STANDARD_TRANSACTIONS,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        assert result["period"]["start"] == "2026-03-01"
        assert result["period"]["end"] == "2026-03-31"

    def test_breakdown_is_dict(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert isinstance(result["breakdown"], dict)


class TestSavingsRateAllTransactions:
    def test_income_is_7000(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["income"] == pytest.approx(7_000.0)

    def test_total_saved_is_700(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["total_saved"] == pytest.approx(700.0)

    def test_savings_rate_is_10_percent(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["savings_rate_pct"] == pytest.approx(10.0)

    def test_only_positive_income_transactions_counted(self):
        txns = [
            _txn("2026-03-01", 3_000.00, "income"),
            _txn("2026-03-10", 1_000.00, "refund"),
            _txn("2026-03-15", -300.00, "savings"),
        ]
        result = calculate_savings_rate(txns)
        assert result["income"] == pytest.approx(3_000.0)

    def test_savings_uses_abs_of_negative_amounts(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-01", -500.00, "savings"),
        ]
        result = calculate_savings_rate(txns)
        assert result["total_saved"] == pytest.approx(500.0)
        assert result["savings_rate_pct"] == pytest.approx(10.0)


class TestSavingsRateDateFilter:
    def _multi_month_txns(self):
        return [
            _txn("2026-02-01", 3_500.00, "income"),
            _txn("2026-02-14", -200.00, "savings"),
            _txn("2026-03-01", 3_500.00, "income"),
            _txn("2026-03-14", -500.00, "retirement"),
        ]

    def test_start_date_excludes_earlier_transactions(self):
        txns = self._multi_month_txns()
        result = calculate_savings_rate(txns, start_date=date(2026, 3, 1))
        assert result["income"] == pytest.approx(3_500.0)
        assert result["total_saved"] == pytest.approx(500.0)

    def test_end_date_excludes_later_transactions(self):
        txns = self._multi_month_txns()
        result = calculate_savings_rate(txns, end_date=date(2026, 2, 28))
        assert result["income"] == pytest.approx(3_500.0)
        assert result["total_saved"] == pytest.approx(200.0)

    def test_both_dates_narrow_to_range(self):
        txns = self._multi_month_txns()
        result = calculate_savings_rate(
            txns, start_date=date(2026, 3, 1), end_date=date(2026, 3, 31)
        )
        assert result["income"] == pytest.approx(3_500.0)
        assert result["total_saved"] == pytest.approx(500.0)
        assert result["savings_rate_pct"] == pytest.approx(round(500 / 3500 * 100, 1))

    def test_start_date_is_inclusive(self):
        txns = [_txn("2026-03-01", 2_000.00, "income")]
        result = calculate_savings_rate(txns, start_date=date(2026, 3, 1))
        assert result["income"] == pytest.approx(2_000.0)

    def test_end_date_is_inclusive(self):
        txns = [_txn("2026-03-31", 2_000.00, "income")]
        result = calculate_savings_rate(txns, end_date=date(2026, 3, 31))
        assert result["income"] == pytest.approx(2_000.0)

    def test_date_range_that_excludes_all_returns_zero_rate(self):
        result = calculate_savings_rate(
            STANDARD_TRANSACTIONS,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
        assert result["income"] == 0.0
        assert result["total_saved"] == 0.0
        assert result["savings_rate_pct"] == 0.0


class TestSavingsRateZeroIncome:
    def test_zero_income_returns_zero_rate_not_division_error(self):
        txns = [_txn("2026-03-01", -200.00, "savings")]
        result = calculate_savings_rate(txns)
        assert result["savings_rate_pct"] == 0.0

    def test_zero_income_income_field_is_zero(self):
        txns = [_txn("2026-03-01", -200.00, "savings")]
        result = calculate_savings_rate(txns)
        assert result["income"] == 0.0

    def test_empty_transactions_zero_rate(self):
        result = calculate_savings_rate([])
        assert result["income"] == 0.0
        assert result["total_saved"] == 0.0
        assert result["savings_rate_pct"] == 0.0

    def test_only_expense_transactions_zero_rate(self):
        txns = [
            _txn("2026-03-01", -1_800.00, "housing"),
            _txn("2026-03-07", -100.00, "dining"),
        ]
        result = calculate_savings_rate(txns)
        assert result["savings_rate_pct"] == 0.0


class TestSavingsRateBreakdown:
    def test_savings_key_present_in_breakdown(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-15", -200.00, "savings"),
        ]
        result = calculate_savings_rate(txns)
        assert "savings" in result["breakdown"]

    def test_retirement_key_present_in_breakdown(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-14", -500.00, "retirement"),
        ]
        result = calculate_savings_rate(txns)
        assert "retirement" in result["breakdown"]

    def test_both_savings_and_retirement_present(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert "savings" in result["breakdown"]
        assert "retirement" in result["breakdown"]

    def test_savings_breakdown_amount_is_correct(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["breakdown"]["savings"] == pytest.approx(200.0)

    def test_retirement_breakdown_amount_is_correct(self):
        result = calculate_savings_rate(STANDARD_TRANSACTIONS)
        assert result["breakdown"]["retirement"] == pytest.approx(500.0)

    def test_multiple_transactions_same_savings_category_aggregated(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-01", -100.00, "savings"),
            _txn("2026-03-15", -150.00, "savings"),
        ]
        result = calculate_savings_rate(txns)
        assert result["breakdown"]["savings"] == pytest.approx(250.0)
        assert result["total_saved"] == pytest.approx(250.0)

    def test_non_savings_categories_absent_from_breakdown(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-01", -800.00, "housing"),
            _txn("2026-03-01", -200.00, "savings"),
        ]
        result = calculate_savings_rate(txns)
        assert "housing" not in result["breakdown"]

    def test_no_savings_transactions_empty_breakdown(self):
        txns = [
            _txn("2026-03-01", 5_000.00, "income"),
            _txn("2026-03-01", -800.00, "housing"),
        ]
        result = calculate_savings_rate(txns)
        assert result["breakdown"] == {}
        assert result["total_saved"] == 0.0

    def test_breakdown_values_are_rounded_to_two_decimal_places(self):
        txns = [
            _txn("2026-03-01", 3_000.00, "income"),
            _txn("2026-03-01", -333.333, "savings"),
        ]
        result = calculate_savings_rate(txns)
        val = result["breakdown"]["savings"]
        assert val == round(val, 2)


class TestSavingsRateWithSampleData:
    def test_income_is_7000(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert result["income"] == pytest.approx(7_000.0)

    def test_total_saved_is_700(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert result["total_saved"] == pytest.approx(700.0)

    def test_savings_rate_is_10_percent(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert result["savings_rate_pct"] == pytest.approx(10.0)

    def test_breakdown_contains_savings_and_retirement(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert "savings" in result["breakdown"]
        assert "retirement" in result["breakdown"]

    def test_breakdown_savings_amount_is_200(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert result["breakdown"]["savings"] == pytest.approx(200.0)

    def test_breakdown_retirement_amount_is_500(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_savings_rate(txns)
        assert result["breakdown"]["retirement"] == pytest.approx(500.0)
