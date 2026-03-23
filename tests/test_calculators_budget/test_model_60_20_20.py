"""Tests for the 60/20/20 budget model (structure and calculator behaviour)."""

import pytest

from src.calculators.budget import calculate_budget_breakdown
from src.calculators.budget_models import MODELS

from ._shared import STANDARD_TRANSACTIONS, _txn


class TestModel60_20_20Structure:
    def test_bucket_names_are_needs_wants_savings(self):
        assert {b.name for b in MODELS["60_20_20"].buckets} == {"needs", "wants", "savings"}

    def test_needs_target_pct_is_60(self):
        needs = next(b for b in MODELS["60_20_20"].buckets if b.name == "needs")
        assert needs.target_pct == 60

    def test_wants_target_pct_is_20(self):
        wants = next(b for b in MODELS["60_20_20"].buckets if b.name == "wants")
        assert wants.target_pct == 20

    def test_savings_target_pct_is_20(self):
        savings = next(b for b in MODELS["60_20_20"].buckets if b.name == "savings")
        assert savings.target_pct == 20

    def test_needs_on_track_direction_is_lte(self):
        needs = next(b for b in MODELS["60_20_20"].buckets if b.name == "needs")
        assert needs.on_track_direction == "lte"

    def test_wants_on_track_direction_is_lte(self):
        wants = next(b for b in MODELS["60_20_20"].buckets if b.name == "wants")
        assert wants.on_track_direction == "lte"

    def test_savings_on_track_direction_is_gte(self):
        savings = next(b for b in MODELS["60_20_20"].buckets if b.name == "savings")
        assert savings.on_track_direction == "gte"


class TestModel60_20_20:
    def test_bucket_names_present_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="60_20_20")
        assert set(result["breakdown"].keys()) == {"needs", "wants", "savings"}

    def test_housing_classified_in_needs(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -500.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(500.0)

    def test_dining_classified_in_wants(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -150.00, "dining")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["wants"]["amount"] == pytest.approx(150.0)

    def test_retirement_classified_in_savings(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "retirement")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(200.0)

    def test_target_pct_values_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="60_20_20")
        assert result["breakdown"]["needs"]["target_pct"] == 60
        assert result["breakdown"]["wants"]["target_pct"] == 20
        assert result["breakdown"]["savings"]["target_pct"] == 20

    def test_on_track_needs_when_at_exactly_60pct(self):
        # income=1000, housing=600 → 60.0% → lte 60 → on_track=True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -600.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is True

    def test_off_track_needs_when_above_60pct(self):
        # income=1000, housing=700 → 70.0% → lte 60 → on_track=False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -700.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is False

    def test_on_track_savings_when_meeting_20pct(self):
        # income=1000, savings=200 → 20% → gte 20 → on_track=True
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["savings"]["on_track"] is True

    def test_off_track_savings_when_below_20pct(self):
        # income=1000, savings=100 → 10% → gte 20 → on_track=False
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -100.00, "savings")]
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
        txns = [_txn("2026-03-01", 2_000.00, "income"), _txn("2026-03-01", -600.00, "savings")]
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
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -400.00, "HOUSING")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["amount"] == pytest.approx(400.0)

    @pytest.mark.parametrize(
        "needs_spend,expected_on_track",
        [
            (550.0, True),  # 55% < 60% → on_track
            (600.0, True),  # exactly 60% → on_track (lte is inclusive)
            (601.0, False),  # 60.1% > 60% → off_track
        ],
    )
    def test_needs_boundary_parametrized(self, needs_spend, expected_on_track):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -needs_spend, "housing")]
        result = calculate_budget_breakdown(txns, model_key="60_20_20")
        assert result["breakdown"]["needs"]["on_track"] is expected_on_track
