"""Unit tests for src/loaders/vanguard_loader.py."""

from pathlib import Path

import pytest

from src.loaders.base import BaseLoader
from src.loaders.vanguard_loader import VanguardLoader
from src.models.account import AccountType

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_vanguard.csv"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_dir(tmp_path) -> Path:
    """Copy the sample Vanguard CSV fixture into a fresh temp directory."""
    dest = tmp_path / FIXTURE_CSV.name
    dest.write_bytes(FIXTURE_CSV.read_bytes())
    return tmp_path


# ---------------------------------------------------------------------------
# Structure / inheritance
# ---------------------------------------------------------------------------


class TestVanguardLoaderStructure:
    def test_is_subclass_of_base_loader(self):
        assert issubclass(VanguardLoader, BaseLoader)


# ---------------------------------------------------------------------------
# load_accounts
# ---------------------------------------------------------------------------


class TestVanguardLoaderAccounts:
    def test_returns_one_account(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        accounts = loader.load_accounts()
        assert len(accounts) == 1

    def test_account_id_prefixed_with_vanguard(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.account_id == "vanguard_99999999"

    def test_account_name(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.name == "Vanguard 99999999"

    def test_institution_is_vanguard(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.institution == "Vanguard"

    def test_type_is_investment(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.type == AccountType.INVESTMENT

    def test_subtype_is_brokerage(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.subtype == "brokerage"

    def test_currency_is_usd(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.currency == "USD"

    def test_balance_includes_money_market(self, fixture_dir):
        """Balance must sum ALL position rows, including VMFXX.
        AAPL (750.0) + VMFXX (10.0) = 760.0
        """
        loader = VanguardLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.balance == pytest.approx(760.0)


# ---------------------------------------------------------------------------
# load_holdings
# ---------------------------------------------------------------------------


class TestVanguardLoaderHoldings:
    def test_excludes_vmfxx(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        symbols = {h.symbol for h in loader.load_holdings()}
        assert "VMFXX" not in symbols

    def test_returns_one_holding(self, fixture_dir):
        """Only AAPL should appear — VMFXX is filtered out."""
        loader = VanguardLoader(fixture_dir)
        holdings = loader.load_holdings()
        assert len(holdings) == 1

    def test_holding_symbol(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.symbol == "AAPL"

    def test_holding_shares(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.shares == pytest.approx(5.0)

    def test_holding_current_price(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.current_price == pytest.approx(150.0)

    def test_holding_cost_basis_is_zero(self, fixture_dir):
        """Vanguard exports omit cost basis; must default to 0.0."""
        loader = VanguardLoader(fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.cost_basis_per_share == pytest.approx(0.0)

    def test_holding_account_id(self, fixture_dir):
        loader = VanguardLoader(fixture_dir)
        holding = loader.load_holdings()[0]
        assert holding.account_id == "vanguard_99999999"


# ---------------------------------------------------------------------------
# load_transactions
# ---------------------------------------------------------------------------


class TestVanguardLoaderTransactions:
    def test_returns_no_transactions(self, fixture_dir):
        """Vanguard transactions are portfolio activity and must not appear in
        budget or savings-rate calculations.
        """
        loader = VanguardLoader(fixture_dir)
        assert loader.load_transactions() == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestVanguardLoaderErrors:
    def test_missing_directory_raises_file_not_found_on_accounts(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = VanguardLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_accounts()

    def test_missing_directory_raises_file_not_found_on_holdings(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = VanguardLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_holdings()

    def test_empty_directory_returns_empty(self, tmp_path):
        loader = VanguardLoader(tmp_path)
        assert loader.load_accounts() == []
        assert loader.load_holdings() == []
        assert loader.load_transactions() == []
