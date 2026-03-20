"""Chase CSV importer.

Converts a Chase account CSV export to the Midas transactions.csv format.

Expected Chase headers:
  Transaction Date, Post Date, Description, Category, Type, Amount, Memo
"""

import csv
import sys
from pathlib import Path

from .base import InstitutionImporter, parse_date, write_transactions

REQUIRED_COLUMNS = {"Transaction Date", "Description", "Category", "Amount"}


class ChaseImporter(InstitutionImporter):
    """Import transactions from a Chase CSV export."""

    def import_transactions(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse a Chase CSV and write rows to transactions.csv.

        Chase amounts are already signed: negative values are expenses,
        positive values are credits/payments.
        """
        source = Path(input_path)
        rows: list[dict] = []

        with open(source, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                print(f"WARNING: {input_path} appears to be empty.", file=sys.stderr)
                return 0

            missing = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"Chase CSV is missing expected columns: {missing}. "
                    f"Found: {list(reader.fieldnames)}"
                )

            for i, row in enumerate(reader, start=2):
                # Skip rows where all values are empty
                if not any(v.strip() for v in row.values()):
                    continue

                try:
                    date_str = parse_date(row["Transaction Date"])
                except ValueError as exc:
                    print(
                        f"WARNING: row {i} — skipping bad date: {exc}",
                        file=sys.stderr,
                    )
                    continue

                amount_raw = row["Amount"].strip()
                if not amount_raw:
                    print(
                        f"WARNING: row {i} — skipping row with missing amount.",
                        file=sys.stderr,
                    )
                    continue

                rows.append(
                    {
                        "date": date_str,
                        "amount": amount_raw,
                        "description": row["Description"].strip(),
                        "category": row["Category"].strip(),
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
        """No-op: Chase does not export holdings data."""
        return 0
