"""Unit tests for src/loaders/capital_one_loader.py."""

from pathlib import Path

import pytest

from src.loaders.base import BaseLoader
from src.loaders.capital_one_loader import CapitalOneLoader, _parse_account_name
from src.models.account import AccountType

SAVINGS_FIXTURE = Path(__file__).parent / "fixtures" / "cap1_savings_sample.csv"
CREDIT_FIXTURE = Path(__file__).parent / "fixtures" / "cap1_credit_sample.csv"

# Savings fixture content uses account 9999; first row balance = 12500.00.
# Credit fixture content uses card 0000; row 1 debit $85.50, row 2 credit $25.00.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def savings_dir(tmp_path) -> Path:
    """Temp dir containing only the savings fixture, named to match savings format."""
    dest = tmp_path / "2026-03-19_TestAccount...9999.csv"
    dest.write_bytes(SAVINGS_FIXTURE.read_bytes())
    return tmp_path


@pytest.fixture()
def credit_dir(tmp_path) -> Path:
    """Temp dir containing only the credit card fixture."""
    dest = tmp_path / "2026-03-19_transaction_download.csv"
    dest.write_bytes(CREDIT_FIXTURE.read_bytes())
    return tmp_path


@pytest.fixture()
def both_dir(tmp_path) -> Path:
    """Temp dir with both savings and credit fixtures."""
    (tmp_path / "2026-03-19_TestAccount...9999.csv").write_bytes(SAVINGS_FIXTURE.read_bytes())
    (tmp_path / "2026-03-19_transaction_download.csv").write_bytes(CREDIT_FIXTURE.read_bytes())
    return tmp_path


# ---------------------------------------------------------------------------
# Structure / inheritance
# ---------------------------------------------------------------------------


class TestCapitalOneLoaderStructure:
    def test_is_subclass_of_base_loader(self):
        assert issubclass(CapitalOneLoader, BaseLoader)

    def test_instantiates_with_string_path(self, tmp_path):
        loader = CapitalOneLoader(str(tmp_path))
        assert loader.data_dir == tmp_path

    def test_instantiates_with_path_object(self, tmp_path):
        loader = CapitalOneLoader(tmp_path)
        assert loader.data_dir == tmp_path


# ---------------------------------------------------------------------------
# File detection
# ---------------------------------------------------------------------------


class TestCapitalOneFileDetection:
    def test_detects_savings_format(self, savings_dir):
        loader = CapitalOneLoader(savings_dir)
        classified = loader._iter_csv_files()
        assert len(classified) == 1
        _, file_type = classified[0]
        assert file_type == "savings"

    def test_detects_credit_format(self, credit_dir):
        loader = CapitalOneLoader(credit_dir)
        classified = loader._iter_csv_files()
        assert len(classified) == 1
        _, file_type = classified[0]
        assert file_type == "credit"

    def test_skips_unknown_format(self, tmp_path):
        unknown = tmp_path / "unknown.csv"
        unknown.write_text("Col1,Col2\n1,2\n")
        loader = CapitalOneLoader(tmp_path)
        assert loader._iter_csv_files() == []


# ---------------------------------------------------------------------------
# load_accounts — savings
# ---------------------------------------------------------------------------


class TestCapitalOneLoadAccountsSavings:
    def test_savings_account_id(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        assert any(a.account_id == "cap1_9999" for a in accounts)

    def test_savings_account_name(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.name == "Test Account"

    def test_savings_type_is_depository(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.type == AccountType.DEPOSITORY

    def test_savings_subtype(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.subtype == "savings"

    def test_savings_balance_from_first_row(self, savings_dir):
        """Balance must come from the first data row's Balance column (12500.00)."""
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.balance == pytest.approx(12500.00)

    def test_savings_institution(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.institution == "Capital One"

    def test_savings_currency(self, savings_dir):
        accounts = CapitalOneLoader(savings_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_9999")
        assert acct.currency == "USD"


# ---------------------------------------------------------------------------
# load_accounts — credit card
# ---------------------------------------------------------------------------


class TestCapitalOneLoadAccountsCredit:
    def test_credit_account_id(self, credit_dir):
        accounts = CapitalOneLoader(credit_dir).load_accounts()
        assert any(a.account_id == "cap1_0000" for a in accounts)

    def test_credit_type_is_credit(self, credit_dir):
        accounts = CapitalOneLoader(credit_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_0000")
        assert acct.type == AccountType.CREDIT

    def test_credit_balance_computed_from_transactions(self, credit_dir):
        accounts = CapitalOneLoader(credit_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_0000")
        # fixture: $85.50 debit, $25.00 credit → balance = -(85.50 - 25.00) = -60.50
        assert acct.balance == pytest.approx(-60.50)

    def test_credit_name_is_venture_x(self, credit_dir):
        accounts = CapitalOneLoader(credit_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_0000")
        assert acct.name == "Venture X"

    def test_credit_institution(self, credit_dir):
        accounts = CapitalOneLoader(credit_dir).load_accounts()
        acct = next(a for a in accounts if a.account_id == "cap1_0000")
        assert acct.institution == "Capital One"


# ---------------------------------------------------------------------------
# load_transactions — savings
# ---------------------------------------------------------------------------


class TestCapitalOneLoadTransactionsSavings:
    def test_credit_row_positive_amount(self, savings_dir):
        txns = CapitalOneLoader(savings_dir).load_transactions()
        credit_txns = [t for t in txns if t.account_id == "cap1_9999" and t.amount > 0]
        assert len(credit_txns) >= 1
        assert any(t.amount == pytest.approx(2500.00) for t in credit_txns)

    def test_debit_row_negative_amount(self, savings_dir):
        txns = CapitalOneLoader(savings_dir).load_transactions()
        debit_txns = [t for t in txns if t.account_id == "cap1_9999" and t.amount < 0]
        assert len(debit_txns) >= 1
        assert any(t.amount == pytest.approx(-100.00) for t in debit_txns)

    def test_date_parsed_from_mm_dd_yy(self, savings_dir):
        from datetime import date

        txns = CapitalOneLoader(savings_dir).load_transactions()
        # First fixture row: 03/15/26 → 2026-03-15
        dates = {t.date for t in txns if t.account_id == "cap1_9999"}
        assert date(2026, 3, 15) in dates

    def test_credit_transaction_category_income(self, savings_dir):
        txns = CapitalOneLoader(savings_dir).load_transactions()
        credit_txns = [t for t in txns if t.account_id == "cap1_9999" and t.amount > 0]
        assert all(t.category == "income" for t in credit_txns)

    def test_debit_transaction_category_uncategorized(self, savings_dir):
        txns = CapitalOneLoader(savings_dir).load_transactions()
        debit_txns = [t for t in txns if t.account_id == "cap1_9999" and t.amount < 0]
        assert all(t.category == "uncategorized" for t in debit_txns)


# ---------------------------------------------------------------------------
# load_transactions — credit card
# ---------------------------------------------------------------------------


class TestCapitalOneLoadTransactionsCredit:
    def test_debit_column_negative_amount(self, credit_dir):
        txns = CapitalOneLoader(credit_dir).load_transactions()
        # Whole Foods: Debit $85.50 → amount -85.50
        debit_txns = [t for t in txns if t.amount < 0]
        assert any(t.amount == pytest.approx(-85.50) for t in debit_txns)

    def test_credit_column_positive_amount(self, credit_dir):
        txns = CapitalOneLoader(credit_dir).load_transactions()
        # Amazon refund: Credit $25.00 → amount +25.00
        credit_txns = [t for t in txns if t.amount > 0]
        assert any(t.amount == pytest.approx(25.00) for t in credit_txns)

    def test_category_mapped_from_category_field(self, credit_dir):
        txns = CapitalOneLoader(credit_dir).load_transactions()
        # Whole Foods is "Groceries" → "food"
        whole_foods = next(t for t in txns if "WHOLE FOODS" in t.description)
        assert whole_foods.category == "food"

    def test_shopping_category_mapped(self, credit_dir):
        txns = CapitalOneLoader(credit_dir).load_transactions()
        amazon = next(t for t in txns if "AMAZON" in t.description)
        assert amazon.category == "shopping"


# ---------------------------------------------------------------------------
# load_holdings
# ---------------------------------------------------------------------------


class TestCapitalOneLoadHoldings:
    def test_returns_empty_list(self, both_dir):
        assert CapitalOneLoader(both_dir).load_holdings() == []

    def test_returns_empty_list_for_empty_dir(self, tmp_path):
        assert CapitalOneLoader(tmp_path).load_holdings() == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestCapitalOneErrors:
    def test_missing_directory_raises_file_not_found_on_accounts(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            CapitalOneLoader(missing).load_accounts()

    def test_missing_directory_raises_file_not_found_on_transactions(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            CapitalOneLoader(missing).load_transactions()


# ---------------------------------------------------------------------------
# _parse_account_name helper
# ---------------------------------------------------------------------------


class TestParseAccountName:
    def test_emergency_fund(self):
        assert _parse_account_name("2026-03-19_EmergencyFund...6373(1)") == "Emergency Fund"

    def test_property_taxes(self):
        assert _parse_account_name("2026-03-19_PropertyTaxes...5061") == "Property Taxes"

    def test_single_word(self):
        assert _parse_account_name("2026-03-19_Savings...1234") == "Savings"
