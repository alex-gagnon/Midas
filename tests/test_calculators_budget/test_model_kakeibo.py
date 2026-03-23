"""Tests for the Kakeibo budget model (structure and calculator behaviour)."""

import pytest

from src.calculators.budget import calculate_budget_breakdown
from src.calculators.budget_models import MODELS

from ._shared import STANDARD_TRANSACTIONS, _txn


class TestModelKakeiboStructure:
    def test_has_five_buckets(self):
        assert len(MODELS["kakeibo"].buckets) == 5

    def test_bucket_names_are_correct(self):
        assert {b.name for b in MODELS["kakeibo"].buckets} == {
            "survival",
            "optional",
            "culture",
            "extra",
            "savings",
        }

    def test_savings_bucket_on_track_direction_is_gte(self):
        savings = next(b for b in MODELS["kakeibo"].buckets if b.name == "savings")
        assert savings.on_track_direction == "gte"

    def test_non_savings_buckets_have_no_on_track_direction(self):
        for bucket in (b for b in MODELS["kakeibo"].buckets if b.name != "savings"):
            assert bucket.on_track_direction is None, (
                f"Bucket '{bucket.name}' should have on_track_direction=None"
            )

    def test_all_buckets_have_no_target_pct(self):
        # Kakeibo is purely informational — no numeric targets on any bucket
        for bucket in MODELS["kakeibo"].buckets:
            assert bucket.target_pct is None, f"Bucket '{bucket.name}' should have target_pct=None"

    def test_default_bucket_is_extra(self):
        assert MODELS["kakeibo"].default_bucket == "extra"


class TestModelKakeibo:
    def test_bucket_names_present_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert set(result["breakdown"].keys()) == {
            "survival",
            "optional",
            "culture",
            "extra",
            "savings",
        }

    def test_housing_classified_in_survival(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -800.00, "housing")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["survival"]["amount"] == pytest.approx(800.0)

    def test_dining_classified_in_optional(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -120.00, "dining")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["optional"]["amount"] == pytest.approx(120.0)

    def test_education_classified_in_culture(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -80.00, "education")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["culture"]["amount"] == pytest.approx(80.0)

    def test_gifts_classified_in_culture(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -50.00, "gifts")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["culture"]["amount"] == pytest.approx(50.0)

    def test_debt_payment_classified_in_extra(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "debt_payment")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["extra"]["amount"] == pytest.approx(200.0)

    def test_savings_classified_in_savings(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -150.00, "savings")]
        result = calculate_budget_breakdown(txns, model_key="kakeibo")
        assert result["breakdown"]["savings"]["amount"] == pytest.approx(150.0)

    def test_retirement_classified_in_savings(self):
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -300.00, "retirement")]
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
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -200.00, "savings")]
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
        txns = [_txn("2026-03-01", 1_000.00, "income"), _txn("2026-03-01", -500.00, "housing")]
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
            "model",
            "period",
            "income",
            "total_expenses",
            "remaining",
            "breakdown",
        }

    def test_model_info_in_result(self):
        result = calculate_budget_breakdown(STANDARD_TRANSACTIONS, model_key="kakeibo")
        assert result["model"]["key"] == "kakeibo"
        assert result["model"]["name"] == "Kakeibo"
