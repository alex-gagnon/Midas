import csv
from datetime import date
from pathlib import Path

from ..models.account import Account, AccountType
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader


class CSVLoader(BaseLoader):
    """Loads financial data from a directory of CSV files.

    Expected files:
      accounts.csv     — account_id, name, institution, type, subtype, balance, currency
      transactions.csv — date, amount, description, category, account_id
      holdings.csv     — account_id, symbol, name, shares, cost_basis_per_share, current_price
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_accounts(self) -> list[Account]:
        accounts = []
        with open(self.data_dir / "accounts.csv", newline="") as f:
            for row in csv.DictReader(f):
                accounts.append(
                    Account(
                        account_id=row["account_id"],
                        name=row["name"],
                        institution=row["institution"],
                        type=AccountType(row["type"]),
                        subtype=row["subtype"],
                        balance=float(row["balance"]),
                        currency=row.get("currency", "USD"),
                    )
                )
        return accounts

    def load_transactions(self) -> list[Transaction]:
        transactions = []
        with open(self.data_dir / "transactions.csv", newline="") as f:
            for row in csv.DictReader(f):
                transactions.append(
                    Transaction(
                        date=date.fromisoformat(row["date"]),
                        amount=float(row["amount"]),
                        description=row["description"],
                        category=row["category"],
                        account_id=row["account_id"],
                    )
                )
        return transactions

    def load_holdings(self) -> list[Holding]:
        holdings = []
        path = self.data_dir / "holdings.csv"
        if not path.exists():
            return holdings
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                holdings.append(
                    Holding(
                        account_id=row["account_id"],
                        symbol=row["symbol"],
                        name=row["name"],
                        shares=float(row["shares"]),
                        cost_basis_per_share=float(row["cost_basis_per_share"]),
                        current_price=float(row["current_price"]),
                    )
                )
        return holdings
