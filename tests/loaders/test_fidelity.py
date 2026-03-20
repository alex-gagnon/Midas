"""Unit tests for src/loaders/fidelity_loader.py."""

from pathlib import Path

import pytest

from src.loaders.base import BaseLoader
from src.loaders.fidelity_loader import FidelityLoader
from src.models.account import AccountType

# Path to the checked-in fixture file (name must match Portfolio_Positions_*.csv glob)
FIXTURE_CSV = Path(__file__).parent.parent / "fixtures" / "Portfolio_Positions_sample.csv"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_dir(tmp_path) -> Path:
    """Copy the sample Fidelity CSV fixture into a fresh temp directory."""
    dest = tmp_path / FIXTURE_CSV.name
    dest.write_bytes(FIXTURE_CSV.read_bytes())
    return tmp_path


# ---------------------------------------------------------------------------
# Structure / inheritance
# ---------------------------------------------------------------------------


class TestFidelityLoaderStructure:
    def test_is_subclass_of_base_loader(self):
        assert issubclass(FidelityLoader, BaseLoader)

    def test_instantiates_with_string_path(self, tmp_path):
        loader = FidelityLoader(str(tmp_path))
        assert loader.data_dir == tmp_path

    def test_instantiates_with_path_object(self, tmp_path):
        loader = FidelityLoader(tmp_path)
        assert loader.data_dir == tmp_path


# ---------------------------------------------------------------------------
# load_accounts
# ---------------------------------------------------------------------------


class TestFidelityLoaderAccounts:
    def test_returns_correct_count(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        accounts = loader.load_accounts()
        # Fixture has 1 unique account (X99999999)
        assert len(accounts) == 1

    def test_account_id_correct(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.account_id == "X99999999"

    def test_account_name_correct(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.name == "Individual - TOD"

    def test_institution_is_fidelity(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.institution == "Fidelity"

    def test_type_is_investment(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.type == AccountType.INVESTMENT

    def test_subtype_is_lowercased_name(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.subtype == "individual - tod"

    def test_currency_is_usd(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.currency == "USD"

    def test_balance_includes_money_market_and_holdings(self, fixture_dir):
        """Balance must sum all rows: SPAXX** ($10) + NVDA ($750) + FSKAX ($1800) = $2560."""
        loader = FidelityLoader(fixture_dir)
        account = loader.load_accounts()[0]
        assert account.balance == pytest.approx(2560.00)


# ---------------------------------------------------------------------------
# load_holdings
# ---------------------------------------------------------------------------


class TestFidelityLoaderHoldings:
    def test_returns_correct_count(self, fixture_dir):
        """Money-market row must be excluded; fixture has 2 regular holdings."""
        loader = FidelityLoader(fixture_dir)
        holdings = loader.load_holdings()
        assert len(holdings) == 2

    def test_skips_money_market_rows(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        symbols = {h.symbol for h in loader.load_holdings()}
        assert "SPAXX**" not in symbols

    def test_nvda_symbol(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        nvda = next(h for h in loader.load_holdings() if h.symbol == "NVDA")
        assert nvda.symbol == "NVDA"

    def test_nvda_shares(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        nvda = next(h for h in loader.load_holdings() if h.symbol == "NVDA")
        assert nvda.shares == pytest.approx(5.0)

    def test_nvda_current_price(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        nvda = next(h for h in loader.load_holdings() if h.symbol == "NVDA")
        assert nvda.current_price == pytest.approx(150.00)

    def test_nvda_cost_basis_per_share(self, fixture_dir):
        """Average Cost Basis column must be used for cost_basis_per_share."""
        loader = FidelityLoader(fixture_dir)
        nvda = next(h for h in loader.load_holdings() if h.symbol == "NVDA")
        assert nvda.cost_basis_per_share == pytest.approx(100.00)

    def test_fskax_shares(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        fskax = next(h for h in loader.load_holdings() if h.symbol == "FSKAX")
        assert fskax.shares == pytest.approx(10.0)

    def test_fskax_cost_basis_per_share(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        fskax = next(h for h in loader.load_holdings() if h.symbol == "FSKAX")
        assert fskax.cost_basis_per_share == pytest.approx(130.00)

    def test_account_id_on_holdings(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        for h in loader.load_holdings():
            assert h.account_id == "X99999999"


# ---------------------------------------------------------------------------
# load_transactions
# ---------------------------------------------------------------------------


class TestFidelityLoaderTransactions:
    def test_returns_empty_list(self, fixture_dir):
        loader = FidelityLoader(fixture_dir)
        assert loader.load_transactions() == []

    def test_returns_empty_list_for_empty_dir(self, tmp_path):
        loader = FidelityLoader(tmp_path)
        assert loader.load_transactions() == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestFidelityLoaderErrors:
    def test_missing_directory_raises_file_not_found_on_accounts(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = FidelityLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_accounts()

    def test_missing_directory_raises_file_not_found_on_holdings(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        loader = FidelityLoader(missing)
        with pytest.raises(FileNotFoundError):
            loader.load_holdings()

    def test_empty_directory_returns_empty_accounts(self, tmp_path):
        loader = FidelityLoader(tmp_path)
        assert loader.load_accounts() == []

    def test_empty_directory_returns_empty_holdings(self, tmp_path):
        loader = FidelityLoader(tmp_path)
        assert loader.load_holdings() == []
