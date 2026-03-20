"""Unit tests for dataclass models: Account, Holding, Transaction."""

from datetime import date

import pytest

from src.models.account import Account, AccountType
from src.models.holding import Holding
from src.models.transaction import Transaction

# ---------------------------------------------------------------------------
# AccountType
# ---------------------------------------------------------------------------


class TestAccountType:
    def test_string_values(self):
        assert AccountType.DEPOSITORY == "depository"
        assert AccountType.CREDIT == "credit"
        assert AccountType.INVESTMENT == "investment"
        assert AccountType.LOAN == "loan"

    def test_from_string(self):
        assert AccountType("depository") is AccountType.DEPOSITORY
        assert AccountType("investment") is AccountType.INVESTMENT

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            AccountType("savings_account")


# ---------------------------------------------------------------------------
# Account.is_asset
# ---------------------------------------------------------------------------


class TestAccountIsAsset:
    @pytest.mark.parametrize("acct_type", [AccountType.DEPOSITORY, AccountType.INVESTMENT])
    def test_asset_types_return_true(self, acct_type):
        a = Account("x", "X", "Bank", acct_type, "sub", 100.0)
        assert a.is_asset is True

    @pytest.mark.parametrize("acct_type", [AccountType.CREDIT, AccountType.LOAN])
    def test_non_asset_types_return_false(self, acct_type):
        a = Account("x", "X", "Bank", acct_type, "sub", -100.0)
        assert a.is_asset is False


# ---------------------------------------------------------------------------
# Account.is_liability
# ---------------------------------------------------------------------------


class TestAccountIsLiability:
    @pytest.mark.parametrize("acct_type", [AccountType.CREDIT, AccountType.LOAN])
    def test_liability_types_return_true(self, acct_type):
        a = Account("x", "X", "Bank", acct_type, "sub", -100.0)
        assert a.is_liability is True

    @pytest.mark.parametrize("acct_type", [AccountType.DEPOSITORY, AccountType.INVESTMENT])
    def test_non_liability_types_return_false(self, acct_type):
        a = Account("x", "X", "Bank", acct_type, "sub", 100.0)
        assert a.is_liability is False

    def test_is_asset_and_is_liability_are_mutually_exclusive(self):
        """No account type can be both an asset and a liability."""
        for acct_type in AccountType:
            a = Account("x", "X", "Bank", acct_type, "sub", 0.0)
            assert not (a.is_asset and a.is_liability), f"{acct_type} is both asset and liability"

    def test_every_type_is_asset_or_liability(self):
        """Every known account type must be classified as either asset or liability."""
        for acct_type in AccountType:
            a = Account("x", "X", "Bank", acct_type, "sub", 0.0)
            assert a.is_asset or a.is_liability, f"{acct_type} is neither asset nor liability"


# ---------------------------------------------------------------------------
# Account default currency
# ---------------------------------------------------------------------------


class TestAccountCurrency:
    def test_default_currency_is_usd(self):
        a = Account("x", "X", "B", AccountType.DEPOSITORY, "s", 0.0)
        assert a.currency == "USD"

    def test_custom_currency_stored(self):
        a = Account("x", "X", "B", AccountType.DEPOSITORY, "s", 0.0, currency="EUR")
        assert a.currency == "EUR"


# ---------------------------------------------------------------------------
# Holding computed properties
# ---------------------------------------------------------------------------


class TestHoldingCurrentValue:
    def test_basic(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=10.0, cost_basis_per_share=200.0, current_price=250.0
        )
        assert h.current_value == pytest.approx(2_500.0)

    def test_fractional_shares(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=2.5, cost_basis_per_share=100.0, current_price=120.0
        )
        assert h.current_value == pytest.approx(300.0)

    def test_zero_shares(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=0.0, cost_basis_per_share=200.0, current_price=250.0
        )
        assert h.current_value == pytest.approx(0.0)


class TestHoldingCostBasis:
    def test_basic(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=10.0, cost_basis_per_share=200.0, current_price=250.0
        )
        assert h.cost_basis == pytest.approx(2_000.0)

    def test_fractional_shares(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=2.5, cost_basis_per_share=100.0, current_price=120.0
        )
        assert h.cost_basis == pytest.approx(250.0)


class TestHoldingGainLoss:
    def test_gain(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=10.0, cost_basis_per_share=200.0, current_price=250.0
        )
        assert h.gain_loss == pytest.approx(500.0)

    def test_loss(self):
        h = Holding(
            "inv", "BND", "Bond ETF", shares=20.0, cost_basis_per_share=80.0, current_price=75.0
        )
        assert h.gain_loss == pytest.approx(-100.0)

    def test_breakeven(self):
        h = Holding("inv", "X", "X", shares=5.0, cost_basis_per_share=100.0, current_price=100.0)
        assert h.gain_loss == pytest.approx(0.0)


class TestHoldingGainLossPct:
    def test_gain_percentage(self):
        h = Holding(
            "inv", "VTI", "VTI ETF", shares=10.0, cost_basis_per_share=200.0, current_price=250.0
        )
        # gain = 500, cost = 2000, pct = 25.0
        assert h.gain_loss_pct == pytest.approx(25.0)

    def test_loss_percentage(self):
        h = Holding(
            "inv", "BND", "Bond ETF", shares=20.0, cost_basis_per_share=80.0, current_price=75.0
        )
        # gain = -100, cost = 1600, pct = -6.25
        assert h.gain_loss_pct == pytest.approx(-6.25)

    def test_zero_cost_basis_returns_zero(self):
        """Guard against division by zero when cost_basis is 0."""
        h = Holding("inv", "X", "X", shares=10.0, cost_basis_per_share=0.0, current_price=100.0)
        assert h.gain_loss_pct == 0.0

    def test_breakeven_is_zero_pct(self):
        h = Holding("inv", "X", "X", shares=5.0, cost_basis_per_share=100.0, current_price=100.0)
        assert h.gain_loss_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class TestTransaction:
    def test_stores_fields(self):
        t = Transaction(date(2026, 3, 1), 3_500.0, "Salary", "income", "chk_001")
        assert t.date == date(2026, 3, 1)
        assert t.amount == 3_500.0
        assert t.description == "Salary"
        assert t.category == "income"
        assert t.account_id == "chk_001"

    def test_negative_amount_is_expense(self):
        t = Transaction(date(2026, 3, 5), -89.50, "Whole Foods", "groceries", "cc_001")
        assert t.amount < 0

    def test_positive_amount_is_income_or_credit(self):
        t = Transaction(date(2026, 3, 1), 3_500.0, "Direct Deposit", "income", "chk_001")
        assert t.amount > 0
