"""Unit and integration tests for src/loaders/qfx_loader.py."""

from datetime import date
from pathlib import Path

import pytest

from src.loaders.base import BaseLoader
from src.loaders.qfx_loader import QFXLoader
from src.models.account import AccountType

# Path to the checked-in fixture files
FIXTURE_QFX = Path(__file__).parent.parent / "fixtures" / "sample.qfx"
FIXTURE_INVESTMENT_QFX = Path(__file__).parent.parent / "fixtures" / "sample_investment.qfx"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_dir(tmp_path) -> Path:
    """Copy the sample QFX fixture into a fresh temp directory."""
    dest = tmp_path / "sample.qfx"
    dest.write_bytes(FIXTURE_QFX.read_bytes())
    return tmp_path


@pytest.fixture()
def investment_fixture_dir(tmp_path) -> Path:
    """Copy the investment QFX fixture into a fresh temp directory."""
    dest = tmp_path / "sample_investment.qfx"
    dest.write_bytes(FIXTURE_INVESTMENT_QFX.read_bytes())
    return tmp_path


# ---------------------------------------------------------------------------
# Structural / inheritance tests
# ---------------------------------------------------------------------------


class TestQFXLoaderStructure:
    def test_is_subclass_of_base_loader(self):
        assert issubclass(QFXLoader, BaseLoader)

    def test_instantiates_with_string_path(self, tmp_path):
        loader = QFXLoader(str(tmp_path))
        assert loader.data_dir == tmp_path

    def test_instantiates_with_path_object(self, tmp_path):
        loader = QFXLoader(tmp_path)
        assert loader.data_dir == tmp_path


# ---------------------------------------------------------------------------
# load_accounts
# ---------------------------------------------------------------------------


class TestQFXLoaderAccounts:
    def test_returns_one_account(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        accounts = loader.load_accounts()
        assert len(accounts) == 1

    def test_account_id_parsed_correctly(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.account_id == "123456789"

    def test_account_name_is_file_stem(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.name == "sample"

    def test_institution_parsed_correctly(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.institution == "Test Bank"

    def test_balance_parsed_correctly(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.balance == pytest.approx(1500.00)

    def test_checking_maps_to_depository(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.type == AccountType.DEPOSITORY

    def test_subtype_is_lowercase_account_type(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.subtype == "checking"

    def test_currency_defaults_to_usd(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.currency == "USD"


# ---------------------------------------------------------------------------
# load_transactions
# ---------------------------------------------------------------------------


class TestQFXLoaderTransactions:
    def test_returns_correct_count(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        assert len(txns) == 3

    def test_deposit_maps_to_income_category(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        deposit = next(t for t in txns if t.amount > 0)
        assert deposit.category == "income"

    def test_debit_maps_to_uncategorized_category(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        debit = next(t for t in txns if t.description == "GROCERY STORE")
        assert debit.category == "uncategorized"

    def test_check_maps_to_uncategorized_category(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        check = next(t for t in txns if t.description == "RENT CHECK")
        assert check.category == "uncategorized"

    def test_date_parsed_as_date_object(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        for txn in loader.load_transactions():
            assert isinstance(txn.date, date)
            assert not hasattr(txn.date, "hour"), "Expected date, not datetime"

    def test_deposit_date_correct(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        deposit = next(t for t in txns if t.amount > 0)
        assert deposit.date == date(2025, 1, 15)

    def test_deposit_amount_positive(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        deposit = next(t for t in txns if t.description == "PAYROLL DEPOSIT")
        assert deposit.amount == pytest.approx(500.00)

    def test_debit_amount_negative(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        debit = next(t for t in txns if t.description == "GROCERY STORE")
        assert debit.amount == pytest.approx(-75.50)

    def test_check_amount_negative(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        check = next(t for t in txns if t.description == "RENT CHECK")
        assert check.amount == pytest.approx(-200.00)

    def test_account_id_on_transactions(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        for txn in loader.load_transactions():
            assert txn.account_id == "123456789"

    def test_description_populated(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        txns = loader.load_transactions()
        descriptions = {t.description for t in txns}
        assert "PAYROLL DEPOSIT" in descriptions
        assert "GROCERY STORE" in descriptions
        assert "RENT CHECK" in descriptions


# ---------------------------------------------------------------------------
# load_holdings
# ---------------------------------------------------------------------------


class TestQFXLoaderHoldings:
    def test_returns_empty_list(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        assert loader.load_holdings() == []

    def test_returns_empty_list_for_empty_dir(self, tmp_path):
        loader = QFXLoader(tmp_path)
        assert loader.load_holdings() == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestQFXLoaderErrors:
    def test_missing_directory_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = QFXLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_accounts()

    def test_missing_directory_raises_on_transactions(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = QFXLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_transactions()

    def test_empty_directory_returns_empty_accounts(self, tmp_path):
        loader = QFXLoader(tmp_path)
        assert loader.load_accounts() == []

    def test_empty_directory_returns_empty_transactions(self, tmp_path):
        loader = QFXLoader(tmp_path)
        assert loader.load_transactions() == []


# ---------------------------------------------------------------------------
# Investment account support (INVSTMTMSGSRSV1)
# ---------------------------------------------------------------------------


class TestQFXLoaderInvestmentAccount:
    def test_investment_account_type(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        accounts = loader.load_accounts()
        assert len(accounts) == 1
        assert accounts[0].type == AccountType.INVESTMENT

    def test_investment_account_id(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        account = loader.load_accounts()[0]
        assert account.account_id == "INV-TEST-001"

    def test_investment_institution(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        account = loader.load_accounts()[0]
        assert account.institution == "TESTBROKER"

    def test_investment_balance_sums_positions(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        account = loader.load_accounts()[0]
        # Fixture has 1 position: 447.4705 units @ 65.85 = 29465.93
        assert account.balance == pytest.approx(29465.93)

    def test_investment_subtype_is_empty_string(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        account = loader.load_accounts()[0]
        assert account.subtype == ""


class TestQFXLoaderInvestmentHoldings:
    def test_returns_one_holding(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holdings = loader.load_holdings()
        assert len(holdings) == 1

    def test_holding_symbol_from_security_list(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.symbol == "VFFVX"

    def test_holding_name_from_security_list(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert "Vanguard" in holding.name

    def test_holding_shares(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.shares == pytest.approx(447.4705)

    def test_holding_current_price(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.current_price == pytest.approx(65.85)

    def test_holding_cost_basis_is_zero(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.cost_basis_per_share == 0.0

    def test_holding_account_id(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.account_id == "INV-TEST-001"

    def test_bank_account_produces_no_holdings(self, fixture_dir):
        loader = QFXLoader(fixture_dir)
        assert loader.load_holdings() == []


class TestQFXLoaderInvestmentTransactions:
    def test_investment_account_returns_no_transactions(self, investment_fixture_dir):
        """Investment account QFX files (401k etc.) return no transactions.

        Portfolio buys/reinvestments are not personal cash flow and must not
        pollute budget or savings-rate calculations.
        """
        loader = QFXLoader(investment_fixture_dir)
        assert loader.load_transactions() == []

    def test_investment_txn_account_id(self, investment_fixture_dir):
        loader = QFXLoader(investment_fixture_dir)
        for txn in loader.load_transactions():
            assert txn.account_id == "INV-TEST-001"
