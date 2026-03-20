"""Capital One CSV importer.

Handles two Capital One export formats:

1. Credit card:
   Headers: Transaction Date, Posted Date, Card No., Description, Category, Debit, Credit
   Debit = positive expense, Credit = positive income.

2. Savings / checking (360):
   Headers: Account Number, Transaction Description, Transaction Date, Transaction Type, Transaction Amount, Balance
   Transaction Type is "Credit" or "Debit"; Transaction Amount is always positive.
"""

import csv
import sys
from pathlib import Path

from .base import InstitutionImporter, parse_date, write_transactions

_CREDIT_CARD_COLS = {"Transaction Date", "Description", "Debit", "Credit"}
_SAVINGS_COLS = {
    "Transaction Date",
    "Transaction Description",
    "Transaction Type",
    "Transaction Amount",
}


def _detect_format(fieldnames: list[str]) -> str:
    """Return 'credit_card' or 'savings' based on CSV headers."""
    cols = set(fieldnames)
    if _CREDIT_CARD_COLS.issubset(cols):
        return "credit_card"
    if _SAVINGS_COLS.issubset(cols):
        return "savings"
    raise ValueError(f"Unrecognised Capital One CSV format. Headers found: {fieldnames}")


class CapitalOneImporter(InstitutionImporter):
    """Import transactions from a Capital One CSV export."""

    def import_transactions(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse a Capital One CSV and write rows to transactions.csv.

        Auto-detects credit card vs. savings/checking format from headers.
        """
        source = Path(input_path)
        rows: list[dict] = []

        with open(source, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(f"WARNING: {input_path} appears to be empty.", file=sys.stderr)
                return 0

            fmt = _detect_format(list(reader.fieldnames))

            for i, row in enumerate(reader, start=2):
                if not any(v.strip() for v in row.values()):
                    continue

                try:
                    date_str = parse_date(row["Transaction Date"])
                except ValueError as exc:
                    print(f"WARNING: row {i} — skipping bad date: {exc}", file=sys.stderr)
                    continue

                if fmt == "credit_card":
                    credit_str = row["Credit"].strip()
                    debit_str = row["Debit"].strip()
                    try:
                        credit = float(credit_str) if credit_str else 0.0
                        debit = float(debit_str) if debit_str else 0.0
                    except ValueError:
                        print(
                            f"WARNING: row {i} — skipping non-numeric "
                            f"Debit={debit_str!r} / Credit={credit_str!r}.",
                            file=sys.stderr,
                        )
                        continue
                    amount = credit - debit
                    description = row["Description"].strip()
                    category = row.get("Category", "").strip()

                else:  # savings / checking
                    amount_str = row["Transaction Amount"].strip().lstrip("$").replace(",", "")
                    try:
                        amount_abs = float(amount_str) if amount_str else 0.0
                    except ValueError:
                        print(
                            f"WARNING: row {i} — skipping non-numeric amount {amount_str!r}.",
                            file=sys.stderr,
                        )
                        continue
                    tx_type = row["Transaction Type"].strip().lower()
                    amount = amount_abs if tx_type == "credit" else -amount_abs
                    description = row["Transaction Description"].strip()
                    category = ""

                rows.append(
                    {
                        "date": date_str,
                        "amount": str(amount),
                        "description": description,
                        "category": category,
                        "account_id": account_id,
                    }
                )

        output_path = str(Path(output_dir) / "transactions.csv")
        return write_transactions(rows, output_path, mode)

    def import_holdings(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """No-op: Capital One does not export holdings data."""
        return 0
