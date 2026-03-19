"""Unit and integration tests for src/importers/."""

import csv
import textwrap
from io import StringIO
from pathlib import Path

import pytest

from src.importers.base import (
    TRANSACTION_HEADERS,
    parse_date,
    write_transactions,
)
from src.importers.capital_one import CapitalOneImporter
from src.importers.chase import ChaseImporter


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    # --- MM/DD/YYYY ---
    def test_mm_dd_yyyy_standard(self):
        assert parse_date("03/19/2026") == "2026-03-19"

    def test_mm_dd_yyyy_zero_pads_month(self):
        assert parse_date("01/05/2026") == "2026-01-05"

    def test_mm_dd_yyyy_with_leading_spaces(self):
        assert parse_date("  03/19/2026  ") == "2026-03-19"

    # --- MM/DD/YY two-digit year → 20XX ---
    def test_mm_dd_yy_two_digit_year(self):
        assert parse_date("03/19/26") == "2026-03-19"

    def test_mm_dd_yy_year_00(self):
        assert parse_date("01/01/00") == "2000-01-01"

    def test_mm_dd_yy_year_99(self):
        assert parse_date("12/31/99") == "2099-12-31"

    # --- YYYY-MM-DD (ISO / already canonical) ---
    def test_yyyy_mm_dd_passes_through(self):
        assert parse_date("2026-03-19") == "2026-03-19"

    def test_yyyy_mm_dd_with_surrounding_spaces(self):
        assert parse_date("  2026-03-19  ") == "2026-03-19"

    # --- Error cases ---
    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="Empty date string"):
            parse_date("")

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError, match="Empty date string"):
            parse_date("   ")

    def test_unrecognised_slash_format_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date("19/03/2026/extra")

    def test_unrecognised_dash_format_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date("19-03-2026")  # DD-MM-YYYY not supported

    def test_no_separator_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_date("20260319")

    @pytest.mark.parametrize("date_input, expected", [
        ("01/01/2000", "2000-01-01"),
        ("12/31/2025", "2025-12-31"),
        ("07/04/24", "2024-07-04"),
        ("2024-07-04", "2024-07-04"),
    ])
    def test_parametrized_valid_formats(self, date_input, expected):
        assert parse_date(date_input) == expected


# ---------------------------------------------------------------------------
# write_transactions (base utility)
# ---------------------------------------------------------------------------


class TestWriteTransactions:
    def _sample_rows(self):
        return [
            {
                "date": "2026-03-01",
                "amount": "-50.00",
                "description": "Coffee",
                "category": "dining",
                "account_id": "chk_001",
            }
        ]

    def test_creates_file_with_header(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        write_transactions(self._sample_rows(), str(dest), mode="overwrite")
        lines = dest.read_text().splitlines()
        assert lines[0] == ",".join(TRANSACTION_HEADERS)

    def test_returns_row_count(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        n = write_transactions(self._sample_rows(), str(dest), mode="overwrite")
        assert n == 1

    def test_empty_rows_returns_zero_and_no_file(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        n = write_transactions([], str(dest), mode="overwrite")
        assert n == 0
        assert not dest.exists()

    def test_append_mode_does_not_duplicate_header(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        write_transactions(self._sample_rows(), str(dest), mode="overwrite")
        write_transactions(self._sample_rows(), str(dest), mode="append")
        lines = [l for l in dest.read_text().splitlines() if l.strip()]
        header_count = sum(1 for l in lines if l.startswith("date,"))
        assert header_count == 1

    def test_append_mode_adds_rows(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        write_transactions(self._sample_rows(), str(dest), mode="overwrite")
        write_transactions(self._sample_rows(), str(dest), mode="append")
        with open(dest, newline="") as f:
            reader = csv.DictReader(f)
            data_rows = list(reader)
        assert len(data_rows) == 2

    def test_overwrite_mode_truncates_file(self, tmp_path):
        dest = tmp_path / "transactions.csv"
        rows_a = self._sample_rows()
        rows_b = [
            {
                "date": "2026-03-02",
                "amount": "-99.00",
                "description": "Lunch",
                "category": "dining",
                "account_id": "chk_001",
            }
        ]
        write_transactions(rows_a + rows_a + rows_a, str(dest), mode="overwrite")
        write_transactions(rows_b, str(dest), mode="overwrite")
        with open(dest, newline="") as f:
            reader = csv.DictReader(f)
            data_rows = list(reader)
        assert len(data_rows) == 1
        assert data_rows[0]["description"] == "Lunch"


# ---------------------------------------------------------------------------
# ChaseImporter
# ---------------------------------------------------------------------------


def _write_tmp_csv(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"


class TestChaseImporter:
    def test_basic_transaction_imported(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Coffee Shop,Food & Drink,Sale,-4.50,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        n = importer.import_transactions(str(src), "chk_001", str(tmp_path))
        assert n == 1

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/15/2026,03/16/2026,Salary,Income,ACH,3500.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-03-15"

    def test_negative_amount_passes_through(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Groceries,Shopping,Sale,-120.50,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "-120.50"

    def test_positive_amount_passes_through(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/15/2026,03/16/2026,Paycheck,Income,ACH,3500.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "3500.00"

    def test_account_id_written_to_output(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Coffee,Food & Drink,Sale,-4.50,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "my_account_123", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["account_id"] == "my_account_123"

    def test_empty_rows_skipped(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Coffee,Food & Drink,Sale,-4.50,\n"
            + ",,,,,, \n"  # all-whitespace row
            + "03/05/2026,03/06/2026,Dinner,Food & Drink,Sale,-35.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        n = importer.import_transactions(str(src), "chk_001", str(tmp_path))
        assert n == 2

    def test_missing_required_column_raises_value_error(self, tmp_path):
        content = "Date,Description,Amount\n03/01/2026,Coffee,-4.50\n"
        src = _write_tmp_csv(tmp_path, "chase_bad.csv", content)
        importer = ChaseImporter()
        with pytest.raises(ValueError, match="missing expected columns"):
            importer.import_transactions(str(src), "chk_001", str(tmp_path))

    def test_import_holdings_is_noop(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "noop.csv", "")
        importer = ChaseImporter()
        # import_holdings is a no-op and returns 0 without raising
        result = importer.import_holdings(str(src), "chk_001", str(tmp_path))
        assert result == 0

    def test_multiple_transactions_all_written(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Coffee,Food,-4.50,\n".replace("Food,-4.50,", "Food & Drink,Sale,-4.50,")
            + "03/02/2026,03/03/2026,Groceries,Shopping,Sale,-75.00,\n"
            + "03/15/2026,03/16/2026,Paycheck,Income,ACH,3500.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        n = importer.import_transactions(str(src), "chk_001", str(tmp_path))
        assert n == 3

    def test_output_file_is_in_output_dir(self, tmp_path):
        content = (
            CHASE_HEADER
            + "03/01/2026,03/02/2026,Coffee,Food & Drink,Sale,-4.50,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(out_dir))
        assert (out_dir / "transactions.csv").exists()


# ---------------------------------------------------------------------------
# CapitalOneImporter — credit card format
# ---------------------------------------------------------------------------


CAP1_CC_HEADER = (
    "Transaction Date,Posted Date,Card No.,Description,Category,Debit,Credit\n"
)


class TestCapitalOneImporterCreditCard:
    def test_debit_becomes_negative_amount(self, tmp_path):
        content = CAP1_CC_HEADER + "03/01/2026,03/02/2026,1234,Coffee,Dining,4.50,\n"
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "cc_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["amount"]) == pytest.approx(-4.50)

    def test_credit_becomes_positive_amount(self, tmp_path):
        content = CAP1_CC_HEADER + "03/15/2026,03/16/2026,1234,Payment,Payment,,500.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "cc_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["amount"]) == pytest.approx(500.0)

    def test_both_debit_and_credit_row(self, tmp_path):
        """Row with both columns — net = credit - debit."""
        # This is an unusual case but the implementation handles it as credit - debit
        content = CAP1_CC_HEADER + "03/01/2026,03/02/2026,1234,Misc,Misc,10.00,2.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "cc_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        # amount = credit - debit = 2.00 - 10.00 = -8.00
        assert float(rows[0]["amount"]) == pytest.approx(-8.0)

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = CAP1_CC_HEADER + "01/05/2026,01/06/2026,1234,Coffee,Dining,4.50,\n"
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "cc_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-01-05"

    def test_description_written_to_output(self, tmp_path):
        content = CAP1_CC_HEADER + "03/01/2026,03/02/2026,1234,Starbucks Coffee,Dining,4.50,\n"
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "cc_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["description"] == "Starbucks Coffee"

    def test_empty_rows_skipped(self, tmp_path):
        content = (
            CAP1_CC_HEADER
            + "03/01/2026,03/02/2026,1234,Coffee,Dining,4.50,\n"
            + ",,,,,,\n"
            + "03/05/2026,03/06/2026,1234,Dinner,Dining,35.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        n = importer.import_transactions(str(src), "cc_001", str(tmp_path))
        assert n == 2

    def test_row_count_returned(self, tmp_path):
        content = (
            CAP1_CC_HEADER
            + "03/01/2026,03/02/2026,1234,Coffee,Dining,4.50,\n"
            + "03/05/2026,03/06/2026,1234,Dinner,Dining,35.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "cap1_cc.csv", content)
        importer = CapitalOneImporter()
        n = importer.import_transactions(str(src), "cc_001", str(tmp_path))
        assert n == 2


# ---------------------------------------------------------------------------
# CapitalOneImporter — savings / checking (360) format
# ---------------------------------------------------------------------------


CAP1_SAV_HEADER = (
    "Account Number,Transaction Description,Transaction Date,"
    "Transaction Type,Transaction Amount,Balance\n"
)


class TestCapitalOneImporterSavings:
    def test_credit_type_becomes_positive_amount(self, tmp_path):
        content = CAP1_SAV_HEADER + "123456,Interest,03/01/2026,Credit,10.50,1010.50\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["amount"]) == pytest.approx(10.50)

    def test_debit_type_becomes_negative_amount(self, tmp_path):
        content = CAP1_SAV_HEADER + "123456,Withdrawal,03/05/2026,Debit,200.00,800.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["amount"]) == pytest.approx(-200.0)

    def test_description_comes_from_transaction_description_column(self, tmp_path):
        content = CAP1_SAV_HEADER + "123456,ACH Transfer,03/10/2026,Credit,500.00,1300.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["description"] == "ACH Transfer"

    def test_category_is_empty_string_for_savings(self, tmp_path):
        content = CAP1_SAV_HEADER + "123456,Interest,03/01/2026,Credit,10.50,1010.50\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["category"] == ""

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = CAP1_SAV_HEADER + "123456,Deposit,07/04/2026,Credit,1000.00,2000.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-07-04"

    def test_empty_rows_skipped_savings(self, tmp_path):
        content = (
            CAP1_SAV_HEADER
            + "123456,Interest,03/01/2026,Credit,10.50,1010.50\n"
            + ",,,,,\n"
            + "123456,Withdrawal,03/05/2026,Debit,200.00,810.50\n"
        )
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        n = importer.import_transactions(str(src), "sav_001", str(tmp_path))
        assert n == 2

    def test_transaction_type_case_insensitive(self, tmp_path):
        """Transaction Type 'CREDIT' (uppercase) should still produce positive amount."""
        content = CAP1_SAV_HEADER + "123456,Payroll,03/15/2026,CREDIT,3500.00,4500.00\n"
        src = _write_tmp_csv(tmp_path, "cap1_sav.csv", content)
        importer = CapitalOneImporter()
        importer.import_transactions(str(src), "sav_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert float(rows[0]["amount"]) == pytest.approx(3500.0)


# ---------------------------------------------------------------------------
# CapitalOneImporter — format detection
# ---------------------------------------------------------------------------


class TestCapitalOneFormatDetection:
    def test_unrecognised_headers_raise_value_error(self, tmp_path):
        content = "Col1,Col2,Col3\nval1,val2,val3\n"
        src = _write_tmp_csv(tmp_path, "cap1_bad.csv", content)
        importer = CapitalOneImporter()
        with pytest.raises(ValueError, match="Unrecognised Capital One CSV format"):
            importer.import_transactions(str(src), "cc_001", str(tmp_path))

    def test_import_holdings_is_noop(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "noop.csv", "")
        importer = CapitalOneImporter()
        result = importer.import_holdings(str(src), "cc_001", str(tmp_path))
        assert result == 0
