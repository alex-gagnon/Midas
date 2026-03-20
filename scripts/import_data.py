#!/usr/bin/env python3
"""CLI runner for Midas institution importers.

Usage examples:
    python scripts/import_data.py --source chase --input path/to/file.csv \
        --account-id chk_001 --output data/real/

    python scripts/import_data.py --source fidelity --input positions.csv \
        --account-id brok_001 --output data/real/ --type holdings

    python scripts/import_data.py --source pdf --input statement.pdf \
        --account-id chk_001 --output data/real/ --mode overwrite
"""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path when this script is run directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.importers import run_import  # noqa: E402  (after sys.path manipulation)

# ---------------------------------------------------------------------------
# accounts.csv starter template
# ---------------------------------------------------------------------------

_ACCOUNTS_TEMPLATE = """\
# accounts.csv template — fill in and save to {output_dir}/accounts.csv
account_id,name,institution,type,subtype,balance,currency
{account_id},<Friendly Name>,<Institution>,depository,checking,0.00,USD
"""


def _print_accounts_template(output_dir: str, account_id: str) -> None:
    print(
        _ACCOUNTS_TEMPLATE.format(output_dir=output_dir, account_id=account_id),
        end="",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_data",
        description="Import financial CSV/PDF exports into Midas data files.",
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=["chase", "capital_one", "fidelity", "vanguard", "pdf"],
        help="Institution / file format to import.",
    )
    parser.add_argument(
        "--input",
        required=True,
        metavar="PATH",
        help="Path to the source file (CSV or PDF).",
    )
    parser.add_argument(
        "--account-id",
        required=True,
        metavar="ID",
        help="Identifier to tag each output row (e.g. chk_001).",
    )
    parser.add_argument(
        "--output",
        default="data/real/",
        metavar="DIR",
        help="Output directory for Midas CSV files (default: data/real/).",
    )
    parser.add_argument(
        "--mode",
        choices=["append", "overwrite"],
        default="append",
        help="Whether to append to or overwrite existing output files (default: append).",
    )
    parser.add_argument(
        "--type",
        dest="import_type",
        choices=["transactions", "holdings"],
        default=None,
        help=(
            "For fidelity/vanguard: force 'transactions' or 'holdings' mode. "
            "Auto-detected from file headers if omitted."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Warn the user if accounts.csv is missing — they will need it for Midas tools
    accounts_csv = output_dir / "accounts.csv"
    if not accounts_csv.exists():
        print(f"NOTE: {accounts_csv} does not exist yet. Here is a starter template:\n")
        _print_accounts_template(str(output_dir), args.account_id)

    # Validate the input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        rows_written = run_import(
            source=args.source,
            input_path=str(input_path),
            account_id=args.account_id,
            output_dir=str(output_dir),
            mode=args.mode,
            import_type=args.import_type,
        )
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except ImportError:
        # pdfplumber not installed — message already printed by pdf_extractor
        sys.exit(1)

    # Determine which output file was written for the summary message.
    # Holdings mode writes holdings.csv; everything else writes transactions.csv.
    if args.import_type == "holdings":
        out_file = output_dir / "holdings.csv"
    else:
        out_file = output_dir / "transactions.csv"

    print(f"Done. {rows_written} row(s) written to {out_file}.")


if __name__ == "__main__":
    main()
