"""Fidelity portfolio positions CSV loader.

Parses date-stamped ``Portfolio_Positions_*.csv`` exports from Fidelity.
The loader scans ``data_dir`` for any file matching that glob pattern so it
works with any export date without renaming the file.

Money-market rows (Symbol ending with ``**``) contribute to account balance
but are excluded from holdings because they have no share price or quantity.

Footer rows (rows where Account Number is empty or starts with ``"``) are
silently skipped.
"""

import csv
import logging
from pathlib import Path

from ..models.account import Account, AccountType
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader
from .parsing import parse_dollar, parse_float

logger = logging.getLogger(__name__)


class FidelityLoader(BaseLoader):
    """Loads financial data from a Fidelity Portfolio_Positions_*.csv export.

    Args:
        data_dir: Path to the directory containing the Fidelity CSV export.
                  Must exist; raises ``FileNotFoundError`` otherwise.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_position_files(self) -> list[Path]:
        """Glob for Portfolio_Positions_*.csv files in data_dir."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        return list(self.data_dir.glob("Portfolio_Positions_*.csv"))

    @staticmethod
    def _is_footer_row(row: dict) -> bool:
        """Return True for footer/disclaimer rows that should be skipped.

        Footer rows either have an empty Account Number or a long sentence
        value (Fidelity disclaimer text).  Real account IDs are short
        alphanumeric strings with no spaces (e.g. ``Z21968493``).
        """
        acct_num = row.get("Account Number", "").strip()
        if not acct_num:
            return True
        # Disclaimer text is always a long sentence; real IDs are ≤ 20 chars
        # and contain no spaces.
        if " " in acct_num or len(acct_num) > 20:
            return True
        return False

    @staticmethod
    def _is_money_market(row: dict) -> bool:
        """Return True for money-market placeholder rows (Symbol ends with **)."""
        return row.get("Symbol", "").strip().endswith("**")

    def _iter_rows(self) -> list[dict]:
        """Read all position files and yield parsed, non-footer rows."""
        rows = []
        for path in self._iter_position_files():
            try:
                with open(path, newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        if self._is_footer_row(row):
                            continue
                        rows.append(row)
            except Exception as exc:
                logger.warning("Skipping file %s: %s", path, exc)
        return rows

    # ------------------------------------------------------------------
    # BaseLoader interface
    # ------------------------------------------------------------------

    def load_accounts(self) -> list[Account]:
        """Return one Account per unique Account Number found in the export."""
        all_rows = self._iter_rows()

        # Group rows by account id to aggregate balances.
        account_rows: dict[str, list[dict]] = {}
        for row in all_rows:
            acct_id = row["Account Number"].strip()
            account_rows.setdefault(acct_id, []).append(row)

        accounts = []
        for acct_id, rows in account_rows.items():
            # All rows for an account share the same Account Name.
            name = rows[0]["Account Name"].strip()

            # Sum Current Value across all rows — including money-market rows.
            balance = sum(parse_dollar(r.get("Current Value", "")) for r in rows)

            accounts.append(
                Account(
                    account_id=acct_id,
                    name=name,
                    institution="Fidelity",
                    type=AccountType.INVESTMENT,
                    subtype=name.lower(),
                    balance=balance,
                    currency="USD",
                )
            )
        return accounts

    def load_holdings(self) -> list[Holding]:
        """Return one Holding per non-money-market row in the export."""
        holdings = []
        for row in self._iter_rows():
            if self._is_money_market(row):
                continue
            try:
                holdings.append(
                    Holding(
                        account_id=row["Account Number"].strip(),
                        symbol=row["Symbol"].strip(),
                        name=row["Description"].strip(),
                        shares=parse_float(row.get("Quantity", "")),
                        cost_basis_per_share=parse_dollar(row.get("Average Cost Basis", "")),
                        current_price=parse_dollar(row.get("Last Price", "")),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping unparseable holding row %s: %s", row, exc)
        return holdings

    def load_transactions(self) -> list[Transaction]:
        """Fidelity positions exports contain no transactions; always returns []."""
        return []
