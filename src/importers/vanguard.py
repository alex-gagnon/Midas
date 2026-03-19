"""Vanguard CSV importer.

Supports two export formats which are auto-detected from headers:

1. Transaction history export
   Headers: Trade Date, Transaction Description, Investment Name, Symbol,
            Shares, Share Price, Principal Amount, Net Amount
   Date format: MM/DD/YYYY

2. Positions (holdings) export
   Top rows may contain account/disclaimer text that must be skipped.
   The real header row is the first row containing 'Symbol'.
   Typical headers: Account Number, Account Name, Symbol, Share Name,
                    Shares, Share Price, Total Value, ...
"""

import csv
import sys
from pathlib import Path

from .base import InstitutionImporter, parse_date, write_holdings, write_transactions

_TRANSACTION_MARKER = "Trade Date"
_POSITIONS_MARKER = "Symbol"

# Symbols that represent summary/total rows — skip in holdings output
_SKIP_SYMBOLS = {"", "Total", "--"}


def _find_header_row(raw_rows: list[list[str]]) -> int:
    """Return the index of the first row that looks like a CSV header.

    Vanguard positions exports embed account info above the data table.
    The real header is the first row that contains 'Symbol'.
    """
    for i, row in enumerate(raw_rows):
        if any(cell.strip() == "Symbol" for cell in row):
            return i
    return 0


def _detect_mode(fieldnames: list[str]) -> str:
    """Return 'transactions' or 'holdings' based on the header row."""
    if _TRANSACTION_MARKER in fieldnames:
        return "transactions"
    if _POSITIONS_MARKER in fieldnames:
        return "holdings"
    raise ValueError(
        f"Cannot detect Vanguard export mode from headers: {fieldnames}. "
        "Expected 'Trade Date' for transactions or 'Symbol' for positions."
    )


class VanguardImporter(InstitutionImporter):
    """Import transactions or holdings from a Vanguard CSV export."""

    def _auto_detect_and_parse(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str,
        forced_type: str | None = None,
    ) -> int:
        """Read the file, detect its type (unless forced), and dispatch."""
        source = Path(input_path)

        with open(source, newline="", encoding="utf-8-sig") as f:
            raw = list(csv.reader(f))

        if not raw:
            print(f"WARNING: {input_path} is empty.", file=sys.stderr)
            return 0

        header_idx = _find_header_row(raw)
        headers = [cell.strip() for cell in raw[header_idx]]
        data_rows = raw[header_idx + 1 :]

        file_type = forced_type or _detect_mode(headers)

        if file_type == "transactions":
            return self._parse_transactions(headers, data_rows, account_id, output_dir, mode)
        return self._parse_holdings(headers, data_rows, account_id, output_dir, mode)

    def _parse_transactions(
        self,
        headers: list[str],
        data_rows: list[list[str]],
        account_id: str,
        output_dir: str,
        mode: str,
    ) -> int:
        rows: list[dict] = []

        for i, raw_row in enumerate(data_rows, start=2):
            row = dict(zip(headers, [cell.strip() for cell in raw_row]))

            # Skip fully empty rows
            if not any(row.values()):
                continue

            date_raw = row.get("Trade Date", "").strip()
            if not date_raw:
                continue

            try:
                date_str = parse_date(date_raw)
            except ValueError as exc:
                print(f"WARNING: row {i} — skipping bad date: {exc}", file=sys.stderr)
                continue

            amount_raw = (
                row.get("Net Amount", "").strip().replace("$", "").replace(",", "")
            )
            if not amount_raw:
                print(
                    f"WARNING: row {i} — skipping row with missing Net Amount.",
                    file=sys.stderr,
                )
                continue

            rows.append({
                "date": date_str,
                "amount": amount_raw,
                "description": row.get("Transaction Description", "").strip(),
                "category": "",  # Vanguard exports don't include a category column
                "account_id": account_id,
            })

        output_path = str(Path(output_dir) / "transactions.csv")
        return write_transactions(rows, output_path, mode)

    def _parse_holdings(
        self,
        headers: list[str],
        data_rows: list[list[str]],
        account_id: str,
        output_dir: str,
        mode: str,
    ) -> int:
        rows: list[dict] = []

        # Vanguard uses various column names across export versions — handle both
        name_col = "Share Name" if "Share Name" in headers else "Investment Name"

        for i, raw_row in enumerate(data_rows, start=2):
            padded = raw_row + [""] * max(0, len(headers) - len(raw_row))
            row = dict(zip(headers, [cell.strip() for cell in padded]))

            symbol = row.get("Symbol", "").strip()
            if symbol in _SKIP_SYMBOLS:
                continue
            # Skip rows that look like section headers or footers
            if not symbol or symbol.startswith("$"):
                continue

            def clean_num(val: str) -> str:
                return val.replace("$", "").replace(",", "").strip()

            shares_raw = clean_num(row.get("Shares", ""))
            price_raw = clean_num(row.get("Share Price", ""))
            # Vanguard doesn't always export cost basis — leave blank if absent
            cost_raw = clean_num(row.get("Average Cost Basis", ""))

            if not shares_raw or not price_raw:
                print(
                    f"WARNING: row {i} — skipping holding with missing Shares or "
                    f"Share Price (symbol={symbol!r}).",
                    file=sys.stderr,
                )
                continue

            rows.append({
                "account_id": account_id,
                "symbol": symbol,
                "name": row.get(name_col, "").strip(),
                "shares": shares_raw,
                "cost_basis_per_share": cost_raw,
                "current_price": price_raw,
            })

        output_path = str(Path(output_dir) / "holdings.csv")
        return write_holdings(rows, output_path, mode)

    def import_transactions(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse a Vanguard transaction CSV and write rows to transactions.csv."""
        return self._auto_detect_and_parse(
            input_path, account_id, output_dir, mode, forced_type="transactions"
        )

    def import_holdings(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse a Vanguard positions CSV and write rows to holdings.csv."""
        return self._auto_detect_and_parse(
            input_path, account_id, output_dir, mode, forced_type="holdings"
        )

    def import_auto(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Auto-detect Vanguard export type from headers and dispatch."""
        return self._auto_detect_and_parse(
            input_path, account_id, output_dir, mode, forced_type=None
        )
