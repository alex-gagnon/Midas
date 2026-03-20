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

    def test_all_four_models_present(self):
        models = list_budget_models()
        keys = {m["key"] for m in models}
        assert keys == {"50_30_20", "70_20_10", "80_20", "zero_based"}

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
    def test_income_from_sample_is_7000(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_budget_breakdown(txns)
        assert result["income"] == pytest.approx(7_000.0)

    def test_all_buckets_have_non_negative_amounts(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_budget_breakdown(txns)
        for bucket_name, bucket in result["breakdown"].items():
            assert bucket["amount"] >= 0, f"Bucket '{bucket_name}' has negative amount"

    def test_actual_pct_sums_to_total_expense_pct(self, sample_data_dir):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_budget_breakdown(txns)
        total_expense_pct = round(result["total_expenses"] / result["income"] * 100, 1)
        bucket_pct_sum = round(sum(b["actual_pct"] for b in result["breakdown"].values()), 1)
        assert bucket_pct_sum == pytest.approx(total_expense_pct, abs=0.2)  # rounding tolerance

    @pytest.mark.parametrize("model_key", ["50_30_20", "70_20_10", "80_20", "zero_based"])
    def test_all_models_run_without_error(self, sample_data_dir, model_key):
        from src.loaders.csv_loader import CSVLoader

        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        result = calculate_budget_breakdown(txns, model_key=model_key)
        assert result["income"] > 0
