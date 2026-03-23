"""Tests for the 70/20/10 and 80/20 budget models."""

import pytest

from src.calculators.budget import calculate_budget_breakdown

from ._shared import STANDARD_TRANSACTIONS, _txn


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
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -50.00, "gifts")]
        result = calculate_budget_breakdown(txns, model_key="70_20_10")
        assert result["breakdown"]["giving_debt"]["amount"] == pytest.approx(50.0)


class TestModel80_20:
    def test_bucket_names_present(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="80_20")
        assert set(result["breakdown"].keys()) == {"savings", "spending"}

    def test_on_track_savings_at_exactly_20pct(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="80_20")
        assert result["breakdown"]["savings"]["on_track"] is True
