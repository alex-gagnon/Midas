"""Unit tests for src/calculators/debt_payoff.py."""

import datetime

import pytest

from src.calculators.debt_payoff import (
    _MAX_MONTHS,
    DEFAULT_APR_PCT,
    _payoff_month_label,
    _simulate_debt,
    calculate_debt_payoff,
)
from src.models.account import Account, AccountType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _account(
    account_id: str,
    balance: float,
    type: AccountType = AccountType.CREDIT,
    subtype: str = "credit_card",
    name: str = "Test Card",
) -> Account:
    return Account(
        account_id=account_id,
        name=name,
        institution="Test Bank",
        type=type,
        subtype=subtype,
        balance=balance,
    )


# ---------------------------------------------------------------------------
# _payoff_month_label
# ---------------------------------------------------------------------------


class TestPayoffMonthLabel:
    def test_zero_offset_returns_same_month(self):
        start = datetime.date(2026, 3, 19)
        assert _payoff_month_label(start, 0) == "2026-03"

    def test_one_month_offset(self):
        start = datetime.date(2026, 3, 19)
        assert _payoff_month_label(start, 1) == "2026-04"

    def test_rolls_over_year(self):
        start = datetime.date(2026, 11, 1)
        assert _payoff_month_label(start, 2) == "2027-01"

    def test_twelve_months_returns_same_month_next_year(self):
        start = datetime.date(2026, 3, 1)
        assert _payoff_month_label(start, 12) == "2027-03"

    def test_zero_pads_single_digit_month(self):
        start = datetime.date(2026, 1, 1)
        label = _payoff_month_label(start, 0)
        assert label == "2026-01"


# ---------------------------------------------------------------------------
# _simulate_debt
# ---------------------------------------------------------------------------


class TestSimulateDebt:
    """Tests for the internal amortisation simulation."""

    _RATE = (DEFAULT_APR_PCT / 100.0) / 12.0
    _START = datetime.date(2026, 3, 19)

    def test_lump_sum_covers_full_balance_returns_zero_months(self):
        months, interest, date_label = _simulate_debt(
            balance=1_000.0,
            monthly_rate=self._RATE,
            monthly_payment=0.0,
            lump_sum=1_000.0,
            start=self._START,
        )
        assert months == 0
        assert interest == 0.0

    def test_lump_sum_exceeds_balance_still_zero_months(self):
        months, interest, _ = _simulate_debt(
            balance=500.0,
            monthly_rate=self._RATE,
            monthly_payment=0.0,
            lump_sum=600.0,
            start=self._START,
        )
        assert months == 0
        assert interest == 0.0

    def test_payoff_months_positive_for_normal_debt(self):
        months, interest, date_label = _simulate_debt(
            balance=1_000.0,
            monthly_rate=self._RATE,
            monthly_payment=100.0,
            lump_sum=0.0,
            start=self._START,
        )
        assert months > 0
        assert interest > 0.0

    def test_interest_is_rounded_to_two_decimal_places(self):
        _, interest, _ = _simulate_debt(
            balance=1_000.0,
            monthly_rate=self._RATE,
            monthly_payment=100.0,
            lump_sum=0.0,
            start=self._START,
        )
        assert round(interest, 2) == interest

    def test_date_label_format_is_yyyy_mm(self):
        _, _, date_label = _simulate_debt(
            balance=1_000.0,
            monthly_rate=self._RATE,
            monthly_payment=100.0,
            lump_sum=0.0,
            start=self._START,
        )
        assert len(date_label) == 7
        assert date_label[4] == "-"

    def test_exceeding_max_horizon_returns_sentinel(self):
        # Tiny payment that will never pay off the debt within 360 months
        months, _, _ = _simulate_debt(
            balance=1_000_000.0,
            monthly_rate=self._RATE,
            monthly_payment=1.0,
            lump_sum=0.0,
            start=self._START,
        )
        assert months == _MAX_MONTHS


# ---------------------------------------------------------------------------
# calculate_debt_payoff — empty / no debt
# ---------------------------------------------------------------------------


class TestDebtPayoffNoDebts:
    def test_empty_accounts_returns_zero_balance(self):
        result = calculate_debt_payoff([], monthly_payment=500.0)
        assert result["total_balance"] == 0.0

    def test_empty_accounts_returns_empty_debts_list(self):
        result = calculate_debt_payoff([], monthly_payment=500.0)
        assert result["debts"] == []

    def test_empty_accounts_returns_zero_interest(self):
        result = calculate_debt_payoff([], monthly_payment=500.0)
        assert result["total_interest_paid"] == 0.0

    def test_empty_accounts_preserves_monthly_payment(self):
        result = calculate_debt_payoff([], monthly_payment=750.0)
        assert result["total_monthly_payment"] == 750.0

    def test_empty_accounts_projected_date_is_current_month(self):
        result = calculate_debt_payoff([], monthly_payment=500.0)
        today = datetime.date.today()
        expected = today.strftime("%Y-%m")
        assert result["projected_debt_free_date"] == expected

    def test_no_debt_accounts_among_non_debt_accounts(self):
        accounts = [
            _account("dep_001", 5_000.0, type=AccountType.DEPOSITORY, subtype="checking"),
            _account("inv_001", 20_000.0, type=AccountType.INVESTMENT, subtype="brokerage"),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=500.0)
        assert result["total_balance"] == 0.0
        assert result["debts"] == []

    def test_zero_balance_debt_excluded_from_results(self):
        # A credit account with exactly zero balance should be excluded.
        accounts = [_account("cc_001", 0.0, type=AccountType.CREDIT)]
        result = calculate_debt_payoff(accounts, monthly_payment=500.0)
        assert result["debts"] == []
        assert result["total_balance"] == 0.0


# ---------------------------------------------------------------------------
# calculate_debt_payoff — single debt
# ---------------------------------------------------------------------------


class TestDebtPayoffSingleDebt:
    """Tests for a single debt account; balance stored as negative float."""

    def test_single_credit_account_appears_in_debts(self):
        accounts = [_account("cc_001", -2_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=200.0)
        assert len(result["debts"]) == 1
        assert result["debts"][0]["account_id"] == "cc_001"

    def test_negative_balance_converted_to_positive_debt(self):
        accounts = [_account("cc_001", -2_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=200.0)
        assert result["debts"][0]["balance"] == pytest.approx(2_000.0)
        assert result["total_balance"] == pytest.approx(2_000.0)

    def test_payoff_months_positive(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        assert result["debts"][0]["payoff_months"] > 0

    def test_total_interest_positive_for_debt_with_apr(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        assert result["total_interest_paid"] > 0.0

    def test_assumed_apr_is_default_value(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=200.0)
        assert result["debts"][0]["assumed_apr_pct"] == DEFAULT_APR_PCT

    def test_loan_account_type_included(self):
        accounts = [_account("loan_001", -5_000.0, type=AccountType.LOAN, subtype="auto")]
        result = calculate_debt_payoff(accounts, monthly_payment=200.0)
        assert len(result["debts"]) == 1
        assert result["debts"][0]["account_id"] == "loan_001"

    def test_projected_debt_free_date_matches_payoff_date(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        assert result["projected_debt_free_date"] == result["debts"][0]["payoff_date"]

    def test_extra_payment_reduces_payoff_months(self):
        """A lump-sum extra_payment should reduce the number of months to payoff."""
        accounts = [_account("cc_001", -2_000.0)]
        result_no_extra = calculate_debt_payoff(accounts, monthly_payment=150.0, extra_payment=0.0)
        result_with_extra = calculate_debt_payoff(
            accounts, monthly_payment=150.0, extra_payment=500.0
        )
        assert (
            result_with_extra["debts"][0]["payoff_months"]
            < result_no_extra["debts"][0]["payoff_months"]
        )

    def test_extra_payment_larger_than_balance_results_in_zero_months(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=50.0, extra_payment=2_000.0)
        assert result["debts"][0]["payoff_months"] == 0

    def test_monthly_payment_field_echoes_input(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=123.45)
        assert result["total_monthly_payment"] == pytest.approx(123.45)

    def test_interest_math_approximation(self):
        """
        Sanity-check: for a 1000 balance at 20% APR paid off with 100/mo,
        total interest should be above zero and below the principal.
        """
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        interest = result["total_interest_paid"]
        assert 0 < interest < 1_000.0


# ---------------------------------------------------------------------------
# calculate_debt_payoff — multiple debts
# ---------------------------------------------------------------------------


class TestDebtPayoffMultipleDebts:
    def test_multiple_debts_all_appear_in_results(self):
        accounts = [
            _account("cc_001", -3_000.0),
            _account("cc_002", -1_000.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=400.0)
        assert len(result["debts"]) == 2

    def test_total_balance_sums_all_debts(self):
        accounts = [
            _account("cc_001", -3_000.0),
            _account("cc_002", -1_500.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=400.0)
        assert result["total_balance"] == pytest.approx(4_500.0)

    def test_highest_balance_debt_listed_first(self):
        """Avalanche proxy: debt_list is sorted by balance descending."""
        accounts = [
            _account("cc_small", -500.0),
            _account("cc_big", -3_000.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=400.0)
        # cc_big should appear first (highest balance → first in sorted list)
        assert result["debts"][0]["account_id"] == "cc_big"

    def test_extra_payment_applied_to_highest_balance_debt(self):
        """
        extra_payment is a lump sum in month 1 for the highest-balance debt.
        When extra_payment equals the highest-balance debt's balance, that debt
        should show payoff_months == 0 while the smaller debt still has months > 0.
        """
        accounts = [
            _account("cc_big", -2_000.0),
            _account("cc_small", -800.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=200.0, extra_payment=2_000.0)
        big_debt = next(d for d in result["debts"] if d["account_id"] == "cc_big")
        small_debt = next(d for d in result["debts"] if d["account_id"] == "cc_small")
        assert big_debt["payoff_months"] == 0
        assert small_debt["payoff_months"] > 0

    def test_projected_debt_free_date_is_max_payoff_date(self):
        """projected_debt_free_date must be the latest individual payoff date."""
        accounts = [
            _account("cc_big", -5_000.0),
            _account("cc_small", -300.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=300.0)
        all_dates = [d["payoff_date"] for d in result["debts"]]
        assert result["projected_debt_free_date"] == max(all_dates)

    def test_total_interest_sums_all_debts(self):
        accounts = [
            _account("cc_001", -2_000.0),
            _account("cc_002", -1_000.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=400.0)
        per_debt_sum = sum(d["total_interest_paid"] for d in result["debts"])
        assert result["total_interest_paid"] == pytest.approx(per_debt_sum, abs=0.01)

    def test_non_debt_accounts_ignored_in_multi_account_list(self):
        accounts = [
            _account("dep_001", 5_000.0, type=AccountType.DEPOSITORY, subtype="checking"),
            _account("cc_001", -2_000.0, type=AccountType.CREDIT),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=300.0)
        assert len(result["debts"]) == 1
        assert result["total_balance"] == pytest.approx(2_000.0)

    def test_zero_balance_debt_excluded_from_multi_account_list(self):
        accounts = [
            _account("cc_zero", 0.0, type=AccountType.CREDIT),
            _account("cc_real", -1_500.0, type=AccountType.CREDIT),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=300.0)
        ids = [d["account_id"] for d in result["debts"]]
        assert "cc_zero" not in ids
        assert "cc_real" in ids

    def test_surplus_payment_goes_to_highest_balance(self):
        """
        With one large debt and one tiny debt, the large debt receives the surplus
        of monthly_payment after other debts' minimums, while the tiny debt only
        receives its minimum payment (interest + $1/month principal reduction).
        The large debt should pay off much faster than the tiny one.
        """
        accounts = [
            _account("cc_big", -4_000.0),
            _account("cc_tiny", -100.0),
        ]
        result = calculate_debt_payoff(accounts, monthly_payment=500.0)
        big = next(d for d in result["debts"] if d["account_id"] == "cc_big")
        tiny = next(d for d in result["debts"] if d["account_id"] == "cc_tiny")
        # The big debt (receiving ~$497/mo) should pay off far faster than the
        # tiny debt (receiving minimum ~$2.67/mo → only $1 principal reduction/mo)
        assert big["payoff_months"] < tiny["payoff_months"]


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestDebtPayoffReturnStructure:
    def test_top_level_keys_present_with_debts(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        assert set(result.keys()) == {
            "debts",
            "total_balance",
            "total_monthly_payment",
            "projected_debt_free_date",
            "total_interest_paid",
        }

    def test_top_level_keys_present_without_debts(self):
        result = calculate_debt_payoff([], monthly_payment=100.0)
        assert set(result.keys()) == {
            "debts",
            "total_balance",
            "total_monthly_payment",
            "projected_debt_free_date",
            "total_interest_paid",
        }

    def test_per_debt_keys_present(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        debt = result["debts"][0]
        assert set(debt.keys()) == {
            "account_id",
            "name",
            "balance",
            "assumed_apr_pct",
            "payoff_months",
            "payoff_date",
            "total_interest_paid",
        }

    def test_payoff_date_format_is_yyyy_mm(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        date_str = result["debts"][0]["payoff_date"]
        assert len(date_str) == 7
        assert date_str[4] == "-"

    def test_projected_debt_free_date_format_is_yyyy_mm(self):
        accounts = [_account("cc_001", -1_000.0)]
        result = calculate_debt_payoff(accounts, monthly_payment=100.0)
        date_str = result["projected_debt_free_date"]
        assert len(date_str) == 7
        assert date_str[4] == "-"
