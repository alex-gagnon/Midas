"""Shared pytest fixtures for Midas tests."""

import textwrap
from datetime import date
from pathlib import Path

import pytest

from src.models.account import Account, AccountType
from src.models.holding import Holding
from src.models.transaction import Transaction

# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def checking_account():
    return Account(
        account_id="chk_001",
        name="Chase Checking",
        institution="Chase",
        type=AccountType.DEPOSITORY,
        subtype="checking",
        balance=5_000.00,
    )


@pytest.fixture
def savings_account():
    return Account(
        account_id="sav_001",
        name="Marcus HYSA",
        institution="Goldman Sachs",
        type=AccountType.DEPOSITORY,
        subtype="savings",
        balance=10_000.00,
    )


@pytest.fixture
def credit_account():
    return Account(
        account_id="cc_001",
        name="Chase Sapphire",
        institution="Chase",
        type=AccountType.CREDIT,
        subtype="credit_card",
        balance=-1_500.00,
    )


@pytest.fixture
def loan_account():
    return Account(
        account_id="loan_001",
        name="Auto Loan",
        institution="Toyota Financial",
        type=AccountType.LOAN,
        subtype="auto",
        balance=-12_000.00,
    )


@pytest.fixture
def investment_account():
    return Account(
        account_id="inv_001",
        name="Fidelity Brokerage",
        institution="Fidelity",
        type=AccountType.INVESTMENT,
        subtype="brokerage",
        balance=0.0,
    )


@pytest.fixture
def holding_vti():
    """VTI with a gain."""
    return Holding(
        account_id="inv_001",
        symbol="VTI",
        name="Vanguard Total Stock Market ETF",
        shares=10.0,
        cost_basis_per_share=200.00,
        current_price=250.00,
    )


@pytest.fixture
def holding_bnd():
    """BND with a loss."""
    return Holding(
        account_id="inv_001",
        symbol="BND",
        name="Vanguard Total Bond Market ETF",
        shares=20.0,
        cost_basis_per_share=80.00,
        current_price=75.00,
    )


@pytest.fixture
def income_transaction():
    return Transaction(
        date=date(2026, 3, 1),
        amount=3_500.00,
        description="Direct Deposit",
        category="income",
        account_id="chk_001",
    )


@pytest.fixture
def rent_transaction():
    return Transaction(
        date=date(2026, 3, 1),
        amount=-1_800.00,
        description="March Rent",
        category="housing",
        account_id="chk_001",
    )


@pytest.fixture
def dining_transaction():
    return Transaction(
        date=date(2026, 3, 7),
        amount=-50.00,
        description="Dinner",
        category="dining",
        account_id="cc_001",
    )


@pytest.fixture
def retirement_transaction():
    return Transaction(
        date=date(2026, 3, 14),
        amount=-400.00,
        description="Roth IRA Contribution",
        category="retirement",
        account_id="chk_001",
    )


# ---------------------------------------------------------------------------
# Sample data directory
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_data_dir():
    return Path(__file__).parent.parent / "data" / "sample"


@pytest.fixture
def sample_transactions(sample_data_dir):
    from src.loaders.csv_loader import CSVLoader

    return CSVLoader(sample_data_dir).load_transactions()


# ---------------------------------------------------------------------------
# Temporary CSV directory factory for CSVLoader edge-case tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_csv_dir(tmp_path):
    """Returns a factory: call it with CSV content strings to build a data dir."""

    def _build(
        accounts: str = "",
        transactions: str = "",
        holdings: str = "",
    ) -> Path:
        d = tmp_path / "data"
        d.mkdir()
        (d / "accounts.csv").write_text(accounts, encoding="utf-8")
        (d / "transactions.csv").write_text(transactions, encoding="utf-8")
        (d / "holdings.csv").write_text(holdings, encoding="utf-8")
        return d

    return _build


MINIMAL_ACCOUNTS_CSV = textwrap.dedent("""\
    account_id,name,institution,type,subtype,balance,currency
    chk_001,Test Checking,Test Bank,depository,checking,1000.00,USD
    cc_001,Test Card,Test Bank,credit,credit_card,-500.00,USD
""")

MINIMAL_TRANSACTIONS_CSV = textwrap.dedent("""\
    date,amount,description,category,account_id
    2026-01-01,2000.00,Salary,income,chk_001
    2026-01-05,-500.00,Rent,housing,chk_001
    2026-01-10,-100.00,Groceries,groceries,cc_001
""")

MINIMAL_HOLDINGS_CSV = textwrap.dedent("""\
    account_id,symbol,name,shares,cost_basis_per_share,current_price
    inv_001,VTI,Vanguard Total Stock Market ETF,10.0,200.00,250.00
""")
