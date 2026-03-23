"""Tests for the 50/30/20 budget model."""

import pytest

from src.calculators.budget import calculate_budget_breakdown

from ._shared import STANDARD_TRANSACTIONS, _txn


class TestModel50_30_20:
    def test_bucket_names_present(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="50_30_20")
        assert set(result["breakdown"].keys()) == {"needs", "wants", "savings"}

    def test_housing_in_needs(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -400.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(400.0)

    def test_dining_in_wants(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-07", -100.00, "dining")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(100.0)

    def test_savings_in_savings_bucket(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-15", -200.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(200.0)

    def test_on_track_savings_when_meeting_20pct(self):
        # income=1000, savings=200 → 20%, target=20% gte → on_track=True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["on_track"] is True

    def test_off_track_savings_when_below_20pct(self):
        # income=1000, savings=100 → 10%, target=20% gte → on_track=False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -100.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["savings"]["on_track"] is False

    def test_on_track_needs_when_below_50pct(self):
        # income=1000, housing=300 → 30%, target=50% lte → on_track=True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -300.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["on_track"] is True

    def test_off_track_needs_when_above_50pct(self):
        # income=1000, housing=600 → 60%, target=50% lte → on_track=False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -600.00, "housing")]
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
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -300.00, "Housing")]
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
        txns = [_txn("2026-03-01", 2_000.00, "income"), _txn("2026-03-01", -1_000.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="50_30_20")
        assert result["breakdown"]["needs"]["actual_pct"] == pytest.approx(50.0)
