"""Base utilities and abstract base class for institution importers.

Provides:
  - parse_date()           — normalise MM/DD/YYYY or YYYY-MM-DD to YYYY-MM-DD
  - write_transactions()   — write/append rows to transactions.csv
  - write_holdings()       — write/append rows to holdings.csv
  - InstitutionImporter    — ABC that concrete importers must subclass
"""

import csv
from abc import ABC, abstractmethod
from pathlib import Path

# Canonical column order for each output file
TRANSACTION_HEADERS = ["date", "amount", "description", "category", "account_id"]
HOLDING_HEADERS = [
    "account_id",
    "symbol",
    "name",
    "shares",
    "cost_basis_per_share",
    "current_price",
]


def clean_num(val: str) -> str:
    """Strip currency formatting from a numeric string."""
    return val.replace("$", "").replace(",", "").strip()


def _find_header_row(rows: list[list[str]]) -> int:
    """Return the index of the first row containing 'Symbol', fall back to 0."""
    for i, row in enumerate(rows):
        if any(cell.strip() == "Symbol" for cell in row):
            return i
    return 0


def parse_date(s: str) -> str:
    """Return a YYYY-MM-DD string from MM/DD/YYYY, MM/DD/YY, or YYYY-MM-DD input.

    Two-digit years are interpreted as 20XX.
    Raises ValueError for unrecognised formats.
    """
    s = s.strip()
    if not s:
        raise ValueError("Empty date string")
    if "/" in s:
        # Expect MM/DD/YYYY or MM/DD/YY
        parts = s.split("/")
        if len(parts) != 3:
            raise ValueError(f"Unrecognised date format: {s!r}")
        month, day, year = parts
        year = year.strip()
        if len(year) == 2:
            year = "20" + year
        return f"{year}-{month.strip().zfill(2)}-{day.strip().zfill(2)}"
    if "-" in s:
        # Expect YYYY-MM-DD (already canonical) or similar ISO variant
        parts = s.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return s  # already YYYY-MM-DD
        raise ValueError(f"Unrecognised date format: {s!r}")
    raise ValueError(f"Unrecognised date format: {s!r}")


def _file_has_data(path: Path) -> bool:
    """Return True if the file exists and has at least one non-header data row."""
    if not path.exists():
        return False
    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return len(rows) > 1


def write_transactions(rows: list[dict], path: str, mode: str = "append") -> int:
    """Write transaction rows to *path*.

    Args:
        rows:  List of dicts with keys matching TRANSACTION_HEADERS.
        path:  Destination file path.
        mode:  "append" — add rows (write header only if file is new/empty).
               "overwrite" — truncate and rewrite the file from scratch.

    Returns:
        Number of rows written.
    """
    return _write_csv(rows, TRANSACTION_HEADERS, path, mode)


def write_holdings(rows: list[dict], path: str, mode: str = "append") -> int:
    """Write holdings rows to *path*.

    Args:
        rows:  List of dicts with keys matching HOLDING_HEADERS.
        path:  Destination file path.
        mode:  "append" or "overwrite".

    Returns:
        Number of rows written.
    """
    return _write_csv(rows, HOLDING_HEADERS, path, mode)


def _write_csv(rows: list[dict], headers: list[str], path: str, mode: str) -> int:
    """Internal helper — write *rows* to a CSV at *path* with given *headers*."""
    if not rows:
        return 0

    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if mode == "overwrite":
        write_header = True
        open_mode = "w"
    else:
        # Append: write header only when the file doesn't yet exist or is empty
        write_header = not _file_has_data(dest)
        open_mode = "a"

    with open(dest, open_mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    return len(rows)


class InstitutionImporter(ABC):
    """Abstract base class for institution-specific CSV importers."""

    @abstractmethod
    def import_transactions(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse *input_path* and write normalised rows to transactions.csv.

        Returns the number of rows written.
        """

    @abstractmethod
    def import_holdings(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Parse *input_path* and write normalised rows to holdings.csv.

        Returns the number of rows written.
        """

    def import_auto(
        self,
        input_path: str,
        account_id: str,
        output_dir: str,
        mode: str = "append",
    ) -> int:
        """Auto-detect import type and dispatch accordingly.

        Default implementation calls import_transactions.  Importers that
        support multiple file types (e.g. Fidelity, Vanguard) should override
        this method to inspect the file headers and dispatch to the correct
        import method.

        Returns the number of rows written.
        """
        return self.import_transactions(input_path, account_id, output_dir, mode)
