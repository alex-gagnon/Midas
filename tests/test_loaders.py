"""Unit and integration tests for src/loaders/csv_loader.py."""

import textwrap
from datetime import date

import pytest

from src.loaders.csv_loader import CSVLoader
from src.models.account import AccountType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_dir(tmp_path, accounts="", transactions="", holdings=""):
    d = tmp_path / "data"
    d.mkdir()
    (d / "accounts.csv").write_text(accounts, encoding="utf-8")
    (d / "transactions.csv").write_text(transactions, encoding="utf-8")
    (d / "holdings.csv").write_text(holdings, encoding="utf-8")
    return d


ACCOUNTS_CSV = textwrap.dedent("""\
    account_id,name,institution,type,subtype,balance,currency
    chk_001,Test Checking,Test Bank,depository,checking,1000.00,USD
    cc_001,Test Card,Test Bank,credit,credit_card,-500.00,USD
""")

TRANSACTIONS_CSV = textwrap.dedent("""\
    date,amount,description,category,account_id
    2026-01-01,2000.00,Salary,income,chk_001
    2026-01-05,-500.00,Rent,housing,chk_001
    2026-01-10,-100.00,Groceries,groceries,cc_001
""")

HOLDINGS_CSV = textwrap.dedent("""\
    account_id,symbol,name,shares,cost_basis_per_share,current_price
    inv_001,VTI,Vanguard Total Stock Market ETF,10.0,200.00,250.00
    inv_001,BND,Vanguard Total Bond Market ETF,5.0,80.00,75.00
""")


# ---------------------------------------------------------------------------
# load_accounts
# ---------------------------------------------------------------------------


class TestLoadAccounts:
    def test_returns_correct_count(self, tmp_path):
        d = _build_dir(tmp_path, accounts=ACCOUNTS_CSV)
        loader = CSVLoader(d)
        accounts = loader.load_accounts()
        assert len(accounts) == 2

    def test_account_fields_parsed_correctly(self, tmp_path):
        d = _build_dir(tmp_path, accounts=ACCOUNTS_CSV)
        loader = CSVLoader(d)
        chk = next(a for a in loader.load_accounts() if a.account_id == "chk_001")
        assert chk.name == "Test Checking"
        assert chk.institution == "Test Bank"
        assert chk.type == AccountType.DEPOSITORY
        assert chk.subtype == "checking"
        assert chk.balance == pytest.approx(1_000.0)
        assert chk.currency == "USD"

    def test_account_type_parsed_as_enum(self, tmp_path):
        d = _build_dir(tmp_path, accounts=ACCOUNTS_CSV)
        loader = CSVLoader(d)
        accounts = {a.account_id: a for a in loader.load_accounts()}
        assert accounts["chk_001"].type is AccountType.DEPOSITORY
        assert accounts["cc_001"].type is AccountType.CREDIT

    def test_negative_balance_parsed(self, tmp_path):
        d = _build_dir(tmp_path, accounts=ACCOUNTS_CSV)
        loader = CSVLoader(d)
        cc = next(a for a in loader.load_accounts() if a.account_id == "cc_001")
        assert cc.balance == pytest.approx(-500.0)

    def test_all_account_types_load(self, tmp_path):
        csv = textwrap.dedent("""\
            account_id,name,institution,type,subtype,balance,currency
            a,A,B,depository,checking,0,USD
            b,B,B,credit,credit_card,0,USD
            c,C,B,investment,brokerage,0,USD
            d,D,B,loan,auto,0,USD
        """)
        d = _build_dir(tmp_path, accounts=csv)
        loader = CSVLoader(d)
        accounts = loader.load_accounts()
        types = {a.type for a in accounts}
        assert types == {AccountType.DEPOSITORY, AccountType.CREDIT, AccountType.INVESTMENT, AccountType.LOAN}

    def test_missing_file_raises(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        loader = CSVLoader(d)
        with pytest.raises(FileNotFoundError):
            loader.load_accounts()

    def test_default_currency_fallback(self, tmp_path):
        csv = textwrap.dedent("""\
            account_id,name,institution,type,subtype,balance
            chk_001,Test,Bank,depository,checking,100.00
        """)
        d = _build_dir(tmp_path, accounts=csv)
        loader = CSVLoader(d)
        # csv.DictReader returns None for missing optional columns with .get("currency", "USD")
        accounts = loader.load_accounts()
        assert accounts[0].currency == "USD"

    def test_invalid_account_type_raises(self, tmp_path):
        csv = textwrap.dedent("""\
            account_id,name,institution,type,subtype,balance,currency
            chk_001,Test,Bank,INVALID_TYPE,checking,100.00,USD
        """)
        d = _build_dir(tmp_path, accounts=csv)
        loader = CSVLoader(d)
        with pytest.raises(ValueError):
            loader.load_accounts()


# ---------------------------------------------------------------------------
# load_transactions
# ---------------------------------------------------------------------------


class TestLoadTransactions:
    def test_returns_correct_count(self, tmp_path):
        d = _build_dir(tmp_path, transactions=TRANSACTIONS_CSV)
        loader = CSVLoader(d)
        txns = loader.load_transactions()
        assert len(txns) == 3

    def test_transaction_fields_parsed_correctly(self, tmp_path):
        d = _build_dir(tmp_path, transactions=TRANSACTIONS_CSV)
        loader = CSVLoader(d)
        txns = loader.load_transactions()
        salary = next(t for t in txns if t.category == "income")
        assert salary.date == date(2026, 1, 1)
        assert salary.amount == pytest.approx(2_000.0)
        assert salary.description == "Salary"
        assert salary.account_id == "chk_001"

    def test_date_parsed_as_date_object(self, tmp_path):
        d = _build_dir(tmp_path, transactions=TRANSACTIONS_CSV)
        loader = CSVLoader(d)
        for txn in loader.load_transactions():
            assert isinstance(txn.date, date)

    def test_negative_amount_parsed(self, tmp_path):
        d = _build_dir(tmp_path, transactions=TRANSACTIONS_CSV)
        loader = CSVLoader(d)
        expense = next(t for t in loader.load_transactions() if t.category == "housing")
        assert expense.amount == pytest.approx(-500.0)

    def test_missing_file_raises(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        loader = CSVLoader(d)
        with pytest.raises(FileNotFoundError):
            loader.load_transactions()

    def test_invalid_date_raises(self, tmp_path):
        csv = textwrap.dedent("""\
            date,amount,description,category,account_id
            not-a-date,100.00,Test,income,chk_001
        """)
        d = _build_dir(tmp_path, transactions=csv)
        loader = CSVLoader(d)
        with pytest.raises(ValueError):
            loader.load_transactions()


# ---------------------------------------------------------------------------
# load_holdings
# ---------------------------------------------------------------------------


class TestLoadHoldings:
    def test_returns_correct_count(self, tmp_path):
        d = _build_dir(tmp_path, holdings=HOLDINGS_CSV)
        loader = CSVLoader(d)
        holdings = loader.load_holdings()
        assert len(holdings) == 2

    def test_holding_fields_parsed_correctly(self, tmp_path):
        d = _build_dir(tmp_path, holdings=HOLDINGS_CSV)
        loader = CSVLoader(d)
        vti = next(h for h in loader.load_holdings() if h.symbol == "VTI")
        assert vti.account_id == "inv_001"
        assert vti.name == "Vanguard Total Stock Market ETF"
        assert vti.shares == pytest.approx(10.0)
        assert vti.cost_basis_per_share == pytest.approx(200.0)
        assert vti.current_price == pytest.approx(250.0)

    def test_fractional_shares_parsed(self, tmp_path):
        csv = textwrap.dedent("""\
            account_id,symbol,name,shares,cost_basis_per_share,current_price
            inv_001,VTI,VTI ETF,42.5,198.30,261.45
        """)
        d = _build_dir(tmp_path, holdings=csv)
        loader = CSVLoader(d)
        h = loader.load_holdings()[0]
        assert h.shares == pytest.approx(42.5)

    def test_missing_file_raises(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        loader = CSVLoader(d)
        with pytest.raises(FileNotFoundError):
            loader.load_holdings()

    def test_floats_parsed_for_all_numeric_fields(self, tmp_path):
        d = _build_dir(tmp_path, holdings=HOLDINGS_CSV)
        loader = CSVLoader(d)
        for h in loader.load_holdings():
            assert isinstance(h.shares, float)
            assert isinstance(h.cost_basis_per_share, float)
            assert isinstance(h.current_price, float)


# ---------------------------------------------------------------------------
# Integration: sample data
# ---------------------------------------------------------------------------


class TestCSVLoaderWithSampleData:
    def test_loads_all_sample_accounts(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        accounts = loader.load_accounts()
        assert len(accounts) == 7  # chk, sav, cc×2, inv, ira, loan

    def test_loads_all_sample_transactions(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        txns = loader.load_transactions()
        assert len(txns) == 21

    def test_loads_all_sample_holdings(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        holdings = loader.load_holdings()
        assert len(holdings) == 7

    def test_sample_account_ids_are_unique(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        ids = [a.account_id for a in loader.load_accounts()]
        assert len(ids) == len(set(ids))

    def test_sample_investment_accounts_have_zero_balance(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        inv_accounts = [
            a for a in loader.load_accounts()
            if a.type == AccountType.INVESTMENT
        ]
        for a in inv_accounts:
            assert a.balance == 0.0, f"{a.account_id} should have balance=0"

    def test_sample_transactions_have_valid_dates(self, sample_data_dir):
        loader = CSVLoader(sample_data_dir)
        for txn in loader.load_transactions():
            assert isinstance(txn.date, date)
            assert txn.date.year >= 2020
