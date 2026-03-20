"""Capital One CSV loader.

Reads Capital One's native export formats:

* **Savings account CSVs** — one file per account, named with the account's
  last-4 digits embedded in the filename stem.  Header starts with
  ``Account Number,Transaction Description``.

* **Credit card transaction download** — a single file containing all cards.
  Header starts with ``Transaction Date,Posted Date,Card No.``.

The loader globs all ``*.csv`` files in ``data_dir`` and detects each file's
format by inspecting its first line.  Unknown formats are skipped with a
warning.
"""

import csv
import logging
import re
from datetime import date, datetime
from pathlib import Path

from ..models.account import Account, AccountType
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category mapping for credit card transactions
# ---------------------------------------------------------------------------

_CATEGORY_MAP: dict[str, str] = {
    "dining": "food",
    "groceries": "food",
    "supermarkets": "food",
    "gas": "transport",
    "transportation": "transport",
    "healthcare": "healthcare",
    "internet": "utilities",
    "phone/cable": "utilities",
    "shopping": "shopping",
    "entertainment": "entertainment",
    "travel": "entertainment",
}

_SAVINGS_HEADER_PREFIX = "Account Number,Transaction Description"
_CREDIT_HEADER_PREFIX = "Transaction Date,Posted Date,Card No."


def _map_category(raw: str) -> str:
    """Map a Capital One credit card category string to a Midas category."""
    return _CATEGORY_MAP.get(raw.strip().lower(), "uncategorized")


def _parse_account_name(stem: str) -> str:
    """Extract and humanise the account name from a savings CSV filename stem.

    Filename stems follow the pattern ``YYYY-MM-DD_<Name>...<last4>[(...)]``.
    The name portion is the segment between the first ``_`` and the ``...``
    separator.  CamelCase words are split by inserting a space before each
    capital letter that immediately follows a lowercase letter.

    Examples::

        "2026-03-19_EmergencyFund...6373(1)" → "Emergency Fund"
        "2026-03-19_PropertyTaxes...5061"    → "Property Taxes"
    """
    # Isolate the name part between date-prefix underscore and "..."
    match = re.search(r"_([^.]+)\.\.\.", stem)
    if not match:
        # Fallback: use the whole stem minus leading date prefix
        name_raw = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", stem)
    else:
        name_raw = match.group(1)

    # Insert space before each capital letter that follows a lowercase letter
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name_raw)
    return spaced


class CapitalOneLoader(BaseLoader):
    """Loads financial data from Capital One CSV exports.

    Args:
        data_dir: Path to the directory containing Capital One CSV exports.
                  Must exist; raises ``FileNotFoundError`` otherwise.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_dir(self) -> None:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def _classify_file(self, path: Path) -> str | None:
        """Return ``'savings'``, ``'credit'``, or ``None`` for unknown."""
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
        except Exception as exc:
            logger.warning("Could not read file %s: %s", path, exc)
            return None

        if first_line.startswith(_SAVINGS_HEADER_PREFIX):
            return "savings"
        if first_line.startswith(_CREDIT_HEADER_PREFIX):
            return "credit"

        logger.warning("Unrecognised Capital One CSV format in %s — skipping", path)
        return None

    def _iter_csv_files(self) -> list[tuple[Path, str]]:
        """Return a list of ``(path, file_type)`` for all recognised CSVs."""
        self._check_dir()
        results = []
        for path in sorted(self.data_dir.glob("*.csv")):
            file_type = self._classify_file(path)
            if file_type is not None:
                results.append((path, file_type))
        return results

    # ------------------------------------------------------------------
    # BaseLoader interface
    # ------------------------------------------------------------------

    def load_accounts(self) -> list[Account]:
        """Return one Account per savings file plus one per unique card number."""
        accounts: list[Account] = []

        for path, file_type in self._iter_csv_files():
            if file_type == "savings":
                accounts.extend(self._accounts_from_savings(path))
            elif file_type == "credit":
                accounts.extend(self._accounts_from_credit(path))

        return accounts

    def load_transactions(self) -> list[Transaction]:
        """Return all transactions from all recognised Capital One CSV files."""
        transactions: list[Transaction] = []

        for path, file_type in self._iter_csv_files():
            if file_type == "savings":
                transactions.extend(self._transactions_from_savings(path))
            elif file_type == "credit":
                transactions.extend(self._transactions_from_credit(path))

        return transactions

    def load_holdings(self) -> list[Holding]:
        """Capital One exports contain no investment holdings; always returns []."""
        return []

    # ------------------------------------------------------------------
    # Savings file helpers
    # ------------------------------------------------------------------

    def _accounts_from_savings(self, path: Path) -> list[Account]:
        """Parse a single savings CSV and return a one-element Account list."""
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                first_row = next(iter(reader), None)
        except Exception as exc:
            logger.warning("Could not parse savings file %s: %s", path, exc)
            return []

        if first_row is None:
            return []

        try:
            account_number = first_row["Account Number"].strip()
            balance = float(first_row["Balance"])
        except (KeyError, ValueError) as exc:
            logger.warning("Malformed first row in %s: %s", path, exc)
            return []

        return [
            Account(
                account_id=f"cap1_{account_number}",
                name=_parse_account_name(path.stem),
                institution="Capital One",
                type=AccountType.DEPOSITORY,
                subtype="savings",
                balance=balance,
                currency="USD",
            )
        ]

    def _transactions_from_savings(self, path: Path) -> list[Transaction]:
        """Parse all transaction rows from a savings CSV."""
        transactions: list[Transaction] = []
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    txn = self._parse_savings_row(row, path)
                    if txn is not None:
                        transactions.append(txn)
        except Exception as exc:
            logger.warning("Could not parse savings file %s: %s", path, exc)
        return transactions

    def _parse_savings_row(self, row: dict, path: Path) -> Transaction | None:
        """Parse one savings CSV row into a Transaction, or return None on error."""
        try:
            account_number = row["Account Number"].strip()
            txn_type = row["Transaction Type"].strip()
            raw_amount = float(row["Transaction Amount"])
            description = row["Transaction Description"].strip()
            txn_date = datetime.strptime(row["Transaction Date"].strip(), "%m/%d/%y").date()
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed savings row in %s: %s — %s", path, row, exc)
            return None

        if txn_type == "Credit":
            amount = raw_amount
            category = "income"
        else:
            amount = -raw_amount
            category = "uncategorized"

        return Transaction(
            date=txn_date,
            amount=amount,
            description=description,
            category=category,
            account_id=f"cap1_{account_number}",
        )

    # ------------------------------------------------------------------
    # Credit card file helpers
    # ------------------------------------------------------------------

    def _accounts_from_credit(self, path: Path) -> list[Account]:
        """Parse unique card numbers from a credit card CSV and return Accounts.

        Balance is computed as sum(debits) - sum(credits), stored as a negative
        value (liability convention).  This is approximate when the export does
        not cover the full account history.
        """
        debits: dict[str, float] = {}
        credits: dict[str, float] = {}
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    card_no = row.get("Card No.", "").strip()
                    if not card_no:
                        continue
                    debits.setdefault(card_no, 0.0)
                    credits.setdefault(card_no, 0.0)
                    debit_raw = row.get("Debit", "").strip()
                    credit_raw = row.get("Credit", "").strip()
                    if debit_raw:
                        debits[card_no] += float(debit_raw)
                    if credit_raw:
                        credits[card_no] += float(credit_raw)
        except Exception as exc:
            logger.warning("Could not parse credit card file %s: %s", path, exc)
            return []

        return [
            Account(
                account_id=f"cap1_{card_no}",
                name="Venture X",
                institution="Capital One",
                type=AccountType.CREDIT,
                subtype="credit_card",
                balance=-(debits[card_no] - credits[card_no]),
                currency="USD",
            )
            for card_no in sorted(debits)
        ]

    def _transactions_from_credit(self, path: Path) -> list[Transaction]:
        """Parse all transaction rows from a credit card CSV."""
        transactions: list[Transaction] = []
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    txn = self._parse_credit_row(row, path)
                    if txn is not None:
                        transactions.append(txn)
        except Exception as exc:
            logger.warning("Could not parse credit card file %s: %s", path, exc)
        return transactions

    def _parse_credit_row(self, row: dict, path: Path) -> Transaction | None:
        """Parse one credit card CSV row into a Transaction, or return None on error."""
        try:
            card_no = row["Card No."].strip()
            description = row["Description"].strip()
            category = _map_category(row.get("Category", ""))
            txn_date = date.fromisoformat(row["Transaction Date"].strip())

            debit_raw = row.get("Debit", "").strip()
            credit_raw = row.get("Credit", "").strip()

            if credit_raw:
                amount = float(credit_raw)
            elif debit_raw:
                amount = -float(debit_raw)
            else:
                amount = 0.0
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping malformed credit row in %s: %s — %s", path, row, exc)
            return None

        return Transaction(
            date=txn_date,
            amount=amount,
            description=description,
            category=category,
            account_id=f"cap1_{card_no}",
        )
