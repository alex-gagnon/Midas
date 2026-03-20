"""PDF statement extractor.

Uses pdfplumber to scan pages for tables and extract transaction data.
Institution type is auto-detected from the table header row.

Usage:
    from src.importers.pdf_extractor import extract_transactions
    rows_written = extract_transactions("statement.pdf", "chk_001", "data/real/")
"""

import sys
from pathlib import Path

# Inline imports avoid circular dependency with the other importers
from .base import parse_date, write_transactions

try:
    import pdfplumber  # type: ignore[import-untyped]

    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False


# ---------------------------------------------------------------------------
# Institution detection helpers
# ---------------------------------------------------------------------------


def _detect_institution(header: list[str]) -> str | None:
    """Return a short institution key from a table header, or None if unknown."""
    normalized = {cell.strip().lower() for cell in header if cell}
    if "transaction date" in normalized and "amount" in normalized:
        return "chase"
    if "debit" in normalized or "credit" in normalized:
        return "capital_one"
    if "run date" in normalized:
        return "fidelity"
    if "trade date" in normalized:
        return "vanguard"
    return None


# ---------------------------------------------------------------------------
# Row mappers — inline to avoid circular imports
# ---------------------------------------------------------------------------


def _map_chase_row(header: list[str], row: list[str], account_id: str) -> dict | None:
    """Map a Chase-style table row to a transaction dict."""
    r = dict(zip(header, [cell.strip() if cell else "" for cell in row]))
    date_raw = r.get("Transaction Date", "").strip()
    amount_raw = r.get("Amount", "").strip().replace("$", "").replace(",", "")
    if not date_raw or not amount_raw:
        return None
    try:
        date_str = parse_date(date_raw)
    except ValueError:
        return None
    return {
        "date": date_str,
        "amount": amount_raw,
        "description": r.get("Description", "").strip(),
        "category": r.get("Category", "").strip(),
        "account_id": account_id,
    }


def _map_capital_one_row(header: list[str], row: list[str], account_id: str) -> dict | None:
    """Map a Capital One-style table row to a transaction dict."""
    r = dict(zip(header, [cell.strip() if cell else "" for cell in row]))
    date_raw = r.get("Transaction Date", "").strip()
    if not date_raw:
        return None
    try:
        date_str = parse_date(date_raw)
    except ValueError:
        return None
    credit_str = r.get("Credit", "").strip().replace("$", "").replace(",", "")
    debit_str = r.get("Debit", "").strip().replace("$", "").replace(",", "")
    try:
        credit = float(credit_str) if credit_str else 0.0
        debit = float(debit_str) if debit_str else 0.0
    except ValueError:
        return None
    return {
        "date": date_str,
        "amount": str(credit - debit),
        "description": r.get("Description", "").strip(),
        "category": r.get("Category", "").strip(),
        "account_id": account_id,
    }


def _map_fidelity_row(header: list[str], row: list[str], account_id: str) -> dict | None:
    """Map a Fidelity-style table row to a transaction dict."""
    r = dict(zip(header, [cell.strip() if cell else "" for cell in row]))
    date_raw = r.get("Run Date", "").strip()
    amount_raw = r.get("Amount", "").strip().replace("$", "").replace(",", "")
    if not date_raw or not amount_raw:
        return None
    try:
        date_str = parse_date(date_raw)
    except ValueError:
        return None
    return {
        "date": date_str,
        "amount": amount_raw,
        "description": r.get("Description", "").strip(),
        "category": r.get("Action", "").strip(),
        "account_id": account_id,
    }


def _map_vanguard_row(header: list[str], row: list[str], account_id: str) -> dict | None:
    """Map a Vanguard-style table row to a transaction dict."""
    r = dict(zip(header, [cell.strip() if cell else "" for cell in row]))
    date_raw = r.get("Trade Date", "").strip()
    amount_raw = r.get("Net Amount", "").strip().replace("$", "").replace(",", "")
    if not date_raw or not amount_raw:
        return None
    try:
        date_str = parse_date(date_raw)
    except ValueError:
        return None
    return {
        "date": date_str,
        "amount": amount_raw,
        "description": r.get("Transaction Description", "").strip(),
        "category": "",
        "account_id": account_id,
    }


_MAPPER = {
    "chase": _map_chase_row,
    "capital_one": _map_capital_one_row,
    "fidelity": _map_fidelity_row,
    "vanguard": _map_vanguard_row,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_transactions(
    pdf_path: str,
    account_id: str,
    output_dir: str,
    mode: str = "append",
) -> int:
    """Extract transaction rows from a PDF bank statement.

    Opens the PDF with pdfplumber, iterates over all pages, and scans each
    table for a recognised header row.  Rows that cannot be parsed are printed
    to stderr for manual review.

    Args:
        pdf_path:   Path to the PDF statement.
        account_id: Account identifier to tag each output row.
        output_dir: Directory where transactions.csv will be written.
        mode:       "append" or "overwrite".

    Returns:
        Number of rows successfully written.

    Raises:
        ImportError: Propagated if pdfplumber is not installed (after printing
                     a helpful message).
    """
    if not _PDFPLUMBER_AVAILABLE:
        print(
            "ERROR: pdfplumber is not installed. Install it with:\n"
            "  uv pip install pdfplumber\n"
            "or add it to pyproject.toml dependencies.",
            file=sys.stderr,
        )
        raise ImportError("pdfplumber is required for PDF extraction")

    source = Path(pdf_path)
    all_rows: list[dict] = []

    with pdfplumber.open(str(source)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                if not table:
                    continue

                # The first row of each table is treated as the header
                header = [cell.strip() if cell else "" for cell in table[0]]
                institution = _detect_institution(header)

                if institution is None:
                    # Not a transaction table we recognise — skip silently
                    continue

                mapper = _MAPPER[institution]

                for row_idx, row in enumerate(table[1:], start=2):
                    # Skip fully empty rows
                    if not any(cell for cell in row if cell):
                        continue

                    mapped = mapper(header, row, account_id)
                    if mapped is None:
                        print(
                            f"WARNING: page {page_num}, row {row_idx} — could not parse: {row}",
                            file=sys.stderr,
                        )
                        continue

                    all_rows.append(mapped)

    output_path = str(Path(output_dir) / "transactions.csv")
    return write_transactions(all_rows, output_path, mode)
