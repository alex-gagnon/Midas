"""Vanguard portfolio CSV loader.

Parses the Vanguard ``OfxDownload*.csv`` export format, which contains TWO
sections in a single file separated by blank lines:

  1. **Positions** — one row per holding with current value.
  2. **Transactions** — one row per transaction with trade/settlement dates.

Each section starts with its own header row.  The loader detects which section
it is reading by inspecting the second field of the header:

- ``Investment Name`` → positions header
- ``Trade Date`` → transactions header

Money-market rows (Symbol == ``VMFXX``) are excluded from holdings but
included in the account balance calculation.
"""

import csv
import logging
from io import StringIO
from pathlib import Path

from ..models.account import Account, AccountType
from ..models.holding import Holding
from ..models.transaction import Transaction
from .base import BaseLoader
from .parsing import parse_float

logger = logging.getLogger(__name__)

# Symbol for the Vanguard Federal Money Market fund — excluded from holdings
_MONEY_MARKET_SYMBOL = "VMFXX"


class VanguardLoader(BaseLoader):
    """Loads financial data from a Vanguard OfxDownload*.csv export.

    The export file contains two sections (positions and transactions) in one
    file, each with its own header row, separated by blank lines.

    Args:
        data_dir: Path to the directory containing the Vanguard CSV export.
                  Must exist; raises ``FileNotFoundError`` otherwise.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_csv_files(self) -> list[Path]:
        """Glob for *.csv files in data_dir."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        return list(self.data_dir.glob("*.csv"))

    def _parse_sections(self, path: Path) -> tuple[list[dict], list[dict]]:
        """Return (position_rows, transaction_rows) parsed from *path*.

        The file is split into sections by detecting header rows.  A header row
        is identified by its first field being ``Account Number``.  The second
        field then determines the section type:

        - starts with ``Investment`` → positions header
        - starts with ``Trade`` → transactions header

        Blank lines and lines before the first recognised header are skipped.
        Malformed data rows are logged and skipped.
        """
        position_rows: list[dict] = []
        transaction_rows: list[dict] = []

        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            logger.warning("Cannot read Vanguard file %s: %s", path, exc)
            return position_rows, transaction_rows

        # Split into logical sections separated by blank lines.  Each section
        # begins with a header row.
        current_section: str | None = None  # "positions" | "transactions"
        current_header: list[str] | None = None
        current_lines: list[str] = []

        def _flush_section() -> None:
            """Parse accumulated lines using current_header and append to the
            appropriate results list."""
            if current_section is None or not current_header or not current_lines:
                return
            fake_csv = "\n".join(current_lines)
            reader = csv.DictReader(StringIO(fake_csv), fieldnames=current_header)
            for row in reader:
                # Skip rows whose first field doesn't look like an account number
                acct = row.get("Account Number", "").strip()
                if not acct or not acct.isdigit():
                    continue
                if current_section == "positions":
                    position_rows.append(row)
                else:
                    transaction_rows.append(row)

        for raw_line in text.splitlines():
            line = raw_line.rstrip("\n")

            # Blank line — flush accumulated data lines but keep the current
            # section header active.  Vanguard separates multiple accounts'
            # position blocks with blank lines *within* the same section.
            if not line.strip():
                _flush_section()
                current_lines = []
                continue

            # Parse as CSV to inspect fields
            parsed = next(csv.reader([line]))
            if not parsed:
                continue

            first_field = parsed[0].strip()
            second_field = parsed[1].strip() if len(parsed) > 1 else ""

            # Detect header rows
            if first_field == "Account Number":
                # Flush any prior section before starting a new one
                _flush_section()
                current_lines = []
                if second_field.startswith("Investment"):
                    current_section = "positions"
                elif second_field.startswith("Trade"):
                    current_section = "transactions"
                else:
                    current_section = None
                current_header = [f.strip() for f in parsed]
                continue

            # Data row — only collect if we're inside a known section
            if current_section is not None:
                current_lines.append(line)

        # Flush the final section (file doesn't necessarily end with a blank line)
        _flush_section()

        return position_rows, transaction_rows

    def _load_all_sections(self) -> tuple[list[dict], list[dict]]:
        """Aggregate position and transaction rows across all CSV files."""
        all_positions: list[dict] = []
        all_transactions: list[dict] = []
        for path in self._iter_csv_files():
            pos, txn = self._parse_sections(path)
            all_positions.extend(pos)
            all_transactions.extend(txn)
        return all_positions, all_transactions

    # ------------------------------------------------------------------
    # BaseLoader interface
    # ------------------------------------------------------------------

    def load_accounts(self) -> list[Account]:
        """Return one Account per unique Account Number found in the positions section."""
        positions, _ = self._load_all_sections()

        # Group by account number, summing Total Value (includes VMFXX)
        account_totals: dict[str, float] = {}
        for row in positions:
            acct_num = row.get("Account Number", "").strip()
            if not acct_num:
                continue
            value = parse_float(row.get("Total Value", ""))
            account_totals[acct_num] = account_totals.get(acct_num, 0.0) + value

        accounts = []
        for acct_num, balance in account_totals.items():
            accounts.append(
                Account(
                    account_id=f"vanguard_{acct_num}",
                    name=f"Vanguard {acct_num}",
                    institution="Vanguard",
                    type=AccountType.INVESTMENT,
                    subtype="brokerage",
                    balance=balance,
                    currency="USD",
                )
            )
        return accounts

    def load_holdings(self) -> list[Holding]:
        """Return one Holding per non-money-market row in the positions section."""
        positions, _ = self._load_all_sections()

        holdings = []
        for row in positions:
            symbol = row.get("Symbol", "").strip()
            # Skip money-market and rows without a symbol
            if not symbol or symbol == _MONEY_MARKET_SYMBOL:
                continue
            acct_num = row.get("Account Number", "").strip()
            if not acct_num:
                continue
            try:
                holdings.append(
                    Holding(
                        account_id=f"vanguard_{acct_num}",
                        symbol=symbol,
                        name=row.get("Investment Name", "").strip(),
                        shares=parse_float(row.get("Shares", "")),
                        cost_basis_per_share=0.0,  # Vanguard export omits cost basis
                        current_price=parse_float(row.get("Share Price", "")),
                    )
                )
            except Exception as exc:
                logger.warning("Skipping unparseable Vanguard holding row %s: %s", row, exc)
        return holdings

    def load_transactions(self) -> list[Transaction]:
        """Return empty list — Vanguard transactions are portfolio activity (buys,
        sells, reinvestments) that do not represent personal cash flow and should
        not appear in budget or savings-rate calculations.
        """
        return []
