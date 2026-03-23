"""Unit and integration tests for src/importers/."""

import csv
from pathlib import Path

import pytest

from src.importers.base import (
    TRANSACTION_HEADERS,
    _find_header_row,
    clean_num,
    parse_date,
    write_transactions,
)
from src.importers.capital_one import CapitalOneImporter
from src.importers.chase import ChaseImporter
from src.importers.fidelity import FidelityImporter, _detect_mode as fidelity_detect_mode
from src.importers.vanguard import VanguardImporter, _detect_mode as vanguard_detect_mode

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

    @pytest.mark.parametrize(
        "date_input, expected",
        [
            ("01/01/2000", "2000-01-01"),
            ("12/31/2025", "2025-12-31"),
            ("07/04/24", "2024-07-04"),
            ("2024-07-04", "2024-07-04"),
        ],
    )
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
        lines = [line for line in dest.read_text().splitlines() if line.strip()]
        header_count = sum(1 for line in lines if line.startswith("date,"))
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
        content = CHASE_HEADER + "03/01/2026,03/02/2026,Coffee Shop,Food & Drink,Sale,-4.50,\n"
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        n = importer.import_transactions(str(src), "chk_001", str(tmp_path))
        assert n == 1

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = CHASE_HEADER + "03/15/2026,03/16/2026,Salary,Income,ACH,3500.00,\n"
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-03-15"

    def test_negative_amount_passes_through(self, tmp_path):
        content = CHASE_HEADER + "03/01/2026,03/02/2026,Groceries,Shopping,Sale,-120.50,\n"
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "-120.50"

    def test_positive_amount_passes_through(self, tmp_path):
        content = CHASE_HEADER + "03/15/2026,03/16/2026,Paycheck,Income,ACH,3500.00,\n"
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "3500.00"

    def test_account_id_written_to_output(self, tmp_path):
        content = CHASE_HEADER + "03/01/2026,03/02/2026,Coffee,Food & Drink,Sale,-4.50,\n"
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
            + "03/01/2026,03/02/2026,Coffee,Food,-4.50,\n".replace(
                "Food,-4.50,", "Food & Drink,Sale,-4.50,"
            )
            + "03/02/2026,03/03/2026,Groceries,Shopping,Sale,-75.00,\n"
            + "03/15/2026,03/16/2026,Paycheck,Income,ACH,3500.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        importer = ChaseImporter()
        n = importer.import_transactions(str(src), "chk_001", str(tmp_path))
        assert n == 3

    def test_output_file_is_in_output_dir(self, tmp_path):
        content = CHASE_HEADER + "03/01/2026,03/02/2026,Coffee,Food & Drink,Sale,-4.50,\n"
        src = _write_tmp_csv(tmp_path, "chase.csv", content)
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        importer = ChaseImporter()
        importer.import_transactions(str(src), "chk_001", str(out_dir))
        assert (out_dir / "transactions.csv").exists()


# ---------------------------------------------------------------------------
# CapitalOneImporter — credit card format
# ---------------------------------------------------------------------------


CAP1_CC_HEADER = "Transaction Date,Posted Date,Card No.,Description,Category,Debit,Credit\n"


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


# ---------------------------------------------------------------------------
# clean_num
# ---------------------------------------------------------------------------


class TestCleanNum:
    def test_strips_dollar_sign(self):
        assert clean_num("$1234.56") == "1234.56"

    def test_strips_commas(self):
        assert clean_num("1,234.56") == "1234.56"

    def test_strips_dollar_and_commas(self):
        assert clean_num("$1,234,567.89") == "1234567.89"

    def test_strips_leading_and_trailing_whitespace(self):
        assert clean_num("  42.00  ") == "42.00"

    def test_empty_string_returns_empty_string(self):
        assert clean_num("") == ""

    def test_plain_number_unchanged(self):
        assert clean_num("9.99") == "9.99"

    def test_negative_number_unchanged(self):
        assert clean_num("-250.00") == "-250.00"

    def test_negative_with_dollar_sign(self):
        assert clean_num("-$50.00") == "-50.00"

    def test_whitespace_only_returns_empty_string(self):
        assert clean_num("   ") == ""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("$0.00", "0.00"),
            ("$1,000,000.00", "1000000.00"),
            ("  $99  ", "99"),
        ],
    )
    def test_parametrized_currency_strings(self, raw, expected):
        assert clean_num(raw) == expected


# ---------------------------------------------------------------------------
# _find_header_row
# ---------------------------------------------------------------------------


class TestFindHeaderRow:
    def test_returns_zero_when_symbol_in_first_row(self):
        rows = [["Symbol", "Quantity", "Last Price"], ["AAPL", "10", "150.00"]]
        assert _find_header_row(rows) == 0

    def test_returns_correct_index_when_symbol_is_not_first_row(self):
        rows = [
            ["Account Name", "Individual - TOD"],
            ["Account Number", "X99999999"],
            ["Symbol", "Quantity", "Last Price"],
            ["AAPL", "10", "150.00"],
        ]
        assert _find_header_row(rows) == 2

    def test_falls_back_to_zero_when_symbol_absent(self):
        rows = [["Run Date", "Action", "Amount"], ["03/01/2026", "Buy", "-500.00"]]
        assert _find_header_row(rows) == 0

    def test_empty_rows_list_falls_back_to_zero(self):
        assert _find_header_row([]) == 0

    def test_symbol_match_is_exact_not_substring(self):
        # "Symbols" should not match — only exact "Symbol" after strip
        rows = [["Symbols", "Quantity"], ["AAPL", "10"]]
        assert _find_header_row(rows) == 0

    def test_symbol_cell_with_surrounding_whitespace_matches(self):
        rows = [["Preamble"], ["  Symbol  ", "Quantity"]]
        assert _find_header_row(rows) == 1

    def test_returns_first_matching_row_not_last(self):
        rows = [
            ["Symbol", "First"],
            ["Symbol", "Second"],
        ]
        assert _find_header_row(rows) == 0


# ---------------------------------------------------------------------------
# FidelityImporter — _detect_mode
# ---------------------------------------------------------------------------


class TestFidelityDetectMode:
    def test_detects_transactions_mode(self):
        assert fidelity_detect_mode(["Run Date", "Action", "Symbol", "Amount"]) == "transactions"

    def test_detects_holdings_mode(self):
        assert fidelity_detect_mode(["Symbol", "Quantity", "Last Price"]) == "holdings"

    def test_raises_on_unrecognised_headers(self):
        with pytest.raises(ValueError, match="Cannot detect Fidelity export mode"):
            fidelity_detect_mode(["Date", "Description", "Total"])

    def test_transaction_marker_takes_priority_over_positions_markers(self):
        # Edge case: both markers present — transactions wins because it's checked first
        headers = ["Run Date", "Quantity", "Last Price"]
        assert fidelity_detect_mode(headers) == "transactions"


# ---------------------------------------------------------------------------
# FidelityImporter — holdings parsing
# ---------------------------------------------------------------------------


FIDELITY_HOLDINGS_HEADER = "Symbol,Description,Quantity,Last Price,Average Cost Basis\n"


class TestFidelityImporterHoldings:
    def test_basic_holding_imported(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "AAPL,Apple Inc,10,150.00,120.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 1

    def test_numeric_fields_stripped_of_currency_formatting(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + 'NVDA,NVIDIA Corp,5,"$150.00","$100.00"\n'
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        importer.import_holdings(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["current_price"] == "150.00"
        assert rows[0]["cost_basis_per_share"] == "100.00"

    def test_shares_written_correctly(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "VTI,Vanguard Total,42.5,261.45,198.30\n"
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        importer.import_holdings(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["shares"] == "42.5"

    def test_account_id_written_to_output(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "AAPL,Apple Inc,10,150.00,120.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        importer.import_holdings(str(src), "my_account_fid", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["account_id"] == "my_account_fid"

    def test_skip_symbols_excluded(self, tmp_path):
        # "Account Total" and empty symbol rows should be skipped
        content = (
            FIDELITY_HOLDINGS_HEADER
            + "AAPL,Apple Inc,10,150.00,120.00\n"
            + "Account Total,,,,\n"
            + ",,,\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 1

    def test_empty_csv_returns_zero(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "fidelity_empty.csv", "")
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 0

    def test_header_only_returns_zero(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "fidelity_hdr.csv", FIDELITY_HOLDINGS_HEADER)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 0

    def test_holding_with_missing_quantity_is_skipped(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "AAPL,Apple Inc,,150.00,120.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 0

    def test_holding_with_missing_last_price_is_skipped(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "AAPL,Apple Inc,10,,120.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 0

    def test_preamble_rows_before_header_are_skipped(self, tmp_path):
        # Fidelity positions CSVs often have account info rows before the real header
        content = (
            "Account Name,Individual - TOD\n"
            "Account Number,X99999999\n"
            + FIDELITY_HOLDINGS_HEADER
            + "AAPL,Apple Inc,10,150.00,120.00\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_preamble.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        # _find_header_row will not find "Symbol" here because this header uses
        # "Symbol" as a column in FIDELITY_HOLDINGS_HEADER — but the preamble rows
        # do not contain "Symbol", so the real header row is still found correctly.
        assert n == 1

    def test_multiple_holdings_all_written(self, tmp_path):
        content = (
            FIDELITY_HOLDINGS_HEADER
            + "AAPL,Apple Inc,10,150.00,120.00\n"
            + "MSFT,Microsoft Corp,5,400.00,300.00\n"
            + "VTI,Vanguard Total,42.5,261.45,198.30\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_pos.csv", content)
        importer = FidelityImporter()
        n = importer.import_holdings(str(src), "inv_001", str(tmp_path))
        assert n == 3


# ---------------------------------------------------------------------------
# FidelityImporter — transactions parsing
# ---------------------------------------------------------------------------


FIDELITY_TX_HEADER = "Run Date,Action,Symbol,Description,Type,Quantity,Price,Commission,Amount\n"


class TestFidelityImporterTransactions:
    def test_basic_transaction_imported(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        n = importer.import_transactions(str(src), "inv_001", str(tmp_path))
        assert n == 1

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/15/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        importer.import_transactions(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-03-15"

    def test_amount_written_correctly(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        importer.import_transactions(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "-1500.00"

    def test_description_written_correctly(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        importer.import_transactions(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["description"] == "Apple Inc"

    def test_category_comes_from_action_column(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,DIVIDEND RECEIVED,AAPL,Apple Inc,Cash,0,0.00,0.00,50.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        importer.import_transactions(str(src), "inv_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["category"] == "DIVIDEND RECEIVED"

    def test_account_id_written_to_output(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        importer.import_transactions(str(src), "fid_roth_ira", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["account_id"] == "fid_roth_ira"

    def test_row_missing_run_date_is_skipped(self, tmp_path):
        content = (
            FIDELITY_TX_HEADER
            + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
            + ",YOU SOLD,MSFT,Microsoft Corp,Cash,5,400.00,0.00,2000.00\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        n = importer.import_transactions(str(src), "inv_001", str(tmp_path))
        assert n == 1

    def test_row_missing_amount_is_skipped(self, tmp_path):
        content = (
            FIDELITY_TX_HEADER
            + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
            + "03/02/2026,PENDING,MSFT,Microsoft Corp,Cash,5,400.00,0.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        n = importer.import_transactions(str(src), "inv_001", str(tmp_path))
        assert n == 1

    def test_empty_csv_returns_zero(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "fidelity_empty.csv", "")
        importer = FidelityImporter()
        n = importer.import_transactions(str(src), "inv_001", str(tmp_path))
        assert n == 0

    def test_multiple_transactions_all_written(self, tmp_path):
        content = (
            FIDELITY_TX_HEADER
            + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
            + "03/05/2026,YOU SOLD,MSFT,Microsoft Corp,Cash,5,400.00,0.00,2000.00\n"
            + "03/10/2026,DIVIDEND RECEIVED,VTI,Vanguard Total,Cash,0,0.00,0.00,25.00\n"
        )
        src = _write_tmp_csv(tmp_path, "fidelity_tx.csv", content)
        importer = FidelityImporter()
        n = importer.import_transactions(str(src), "inv_001", str(tmp_path))
        assert n == 3


# ---------------------------------------------------------------------------
# FidelityImporter — import_auto mode detection
# ---------------------------------------------------------------------------


class TestFidelityImporterAuto:
    def test_auto_dispatches_to_transactions_when_run_date_present(self, tmp_path):
        content = FIDELITY_TX_HEADER + "03/01/2026,YOU BOUGHT,AAPL,Apple Inc,Cash,10,150.00,0.00,-1500.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_auto.csv", content)
        importer = FidelityImporter()
        n = importer.import_auto(str(src), "inv_001", str(tmp_path))
        assert n == 1
        assert (tmp_path / "transactions.csv").exists()
        assert not (tmp_path / "holdings.csv").exists()

    def test_auto_dispatches_to_holdings_when_symbol_and_price_present(self, tmp_path):
        content = FIDELITY_HOLDINGS_HEADER + "AAPL,Apple Inc,10,150.00,120.00\n"
        src = _write_tmp_csv(tmp_path, "fidelity_auto.csv", content)
        importer = FidelityImporter()
        n = importer.import_auto(str(src), "inv_001", str(tmp_path))
        assert n == 1
        assert (tmp_path / "holdings.csv").exists()
        assert not (tmp_path / "transactions.csv").exists()


# ---------------------------------------------------------------------------
# VanguardImporter — _detect_mode
# ---------------------------------------------------------------------------


class TestVanguardDetectMode:
    def test_detects_transactions_mode(self):
        assert vanguard_detect_mode(["Trade Date", "Transaction Description", "Net Amount"]) == "transactions"

    def test_detects_holdings_mode(self):
        assert vanguard_detect_mode(["Symbol", "Share Name", "Shares", "Share Price"]) == "holdings"

    def test_raises_on_unrecognised_headers(self):
        with pytest.raises(ValueError, match="Cannot detect Vanguard export mode"):
            vanguard_detect_mode(["Date", "Description", "Total"])

    def test_transaction_marker_takes_priority(self):
        # Edge case: both Trade Date and Symbol present
        assert vanguard_detect_mode(["Trade Date", "Symbol", "Net Amount"]) == "transactions"


# ---------------------------------------------------------------------------
# VanguardImporter — holdings parsing
# ---------------------------------------------------------------------------


VANGUARD_HOLDINGS_HEADER = "Account Number,Account Name,Symbol,Share Name,Shares,Share Price,Total Value\n"


class TestVanguardImporterHoldings:
    def test_basic_holding_imported(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_shares_written_correctly(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["shares"] == "5"

    def test_current_price_written_correctly(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["current_price"] == "150.00"

    def test_account_id_written_to_output(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_roth", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["account_id"] == "vanguard_roth"

    def test_skip_symbols_excluded(self, tmp_path):
        # "Total", "--", and empty symbol rows should be skipped
        content = (
            VANGUARD_HOLDINGS_HEADER
            + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
            + "99999999,Brokerage,Total,,,,750.00\n"
            + "99999999,Brokerage,--,,,,\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_dollar_sign_symbol_excluded(self, tmp_path):
        # Symbols starting with "$" are section headers in some Vanguard exports
        content = (
            VANGUARD_HOLDINGS_HEADER
            + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
            + "99999999,Brokerage,$CASH,Money Market,100,1.00,100.00\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_cost_basis_blank_when_column_absent(self, tmp_path):
        # Vanguard does not always export Average Cost Basis
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["cost_basis_per_share"] == ""

    def test_share_name_column_used_as_name(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,VTI,Vanguard Total Stock Market ETF,42.5,261.45,11111.63\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["name"] == "Vanguard Total Stock Market ETF"

    def test_investment_name_column_used_as_fallback_name(self, tmp_path):
        # Some Vanguard exports use "Investment Name" instead of "Share Name"
        header = "Account Number,Account Name,Symbol,Investment Name,Shares,Share Price,Total Value\n"
        content = header + "99999999,Brokerage,VTI,Vanguard Total (Investment Name),42.5,261.45,11111.63\n"
        src = _write_tmp_csv(tmp_path, "vanguard_alt.csv", content)
        importer = VanguardImporter()
        importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "holdings.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["name"] == "Vanguard Total (Investment Name)"

    def test_empty_csv_returns_zero(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "vanguard_empty.csv", "")
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 0

    def test_holding_missing_shares_is_skipped(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,,150.00,0.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_pos.csv", content)
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 0

    def test_preamble_rows_before_symbol_header_are_skipped(self, tmp_path):
        content = (
            "Account Number,99999999\n"
            "Account Name,Brokerage\n"
            + VANGUARD_HOLDINGS_HEADER
            + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_preamble.csv", content)
        importer = VanguardImporter()
        n = importer.import_holdings(str(src), "vanguard_001", str(tmp_path))
        assert n == 1


# ---------------------------------------------------------------------------
# VanguardImporter — transactions parsing
# ---------------------------------------------------------------------------


VANGUARD_TX_HEADER = "Trade Date,Transaction Description,Investment Name,Symbol,Shares,Share Price,Principal Amount,Net Amount\n"


class TestVanguardImporterTransactions:
    def test_basic_transaction_imported(self, tmp_path):
        content = VANGUARD_TX_HEADER + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        n = importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_date_converted_to_yyyy_mm_dd(self, tmp_path):
        content = VANGUARD_TX_HEADER + "07/04/2026,Dividend,Vanguard Fund,VTI,0,0.00,25.00,25.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date"] == "2026-07-04"

    def test_amount_comes_from_net_amount(self, tmp_path):
        content = VANGUARD_TX_HEADER + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-752.50\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["amount"] == "-752.50"

    def test_description_comes_from_transaction_description(self, tmp_path):
        content = VANGUARD_TX_HEADER + "03/01/2026,Dividend Reinvestment,Vanguard Fund,VTI,0,0.00,25.00,25.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["description"] == "Dividend Reinvestment"

    def test_category_is_empty_string(self, tmp_path):
        # Vanguard transaction exports don't include a category column
        content = VANGUARD_TX_HEADER + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["category"] == ""

    def test_account_id_written_to_output(self, tmp_path):
        content = VANGUARD_TX_HEADER + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        importer.import_transactions(str(src), "vanguard_roth_ira", str(tmp_path))
        out = tmp_path / "transactions.csv"
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["account_id"] == "vanguard_roth_ira"

    def test_row_missing_trade_date_is_skipped(self, tmp_path):
        content = (
            VANGUARD_TX_HEADER
            + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
            + ",Buy,Microsoft Corp,MSFT,2,400.00,-800.00,-800.00\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        n = importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_row_missing_net_amount_is_skipped(self, tmp_path):
        content = (
            VANGUARD_TX_HEADER
            + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
            + "03/02/2026,Pending,Microsoft Corp,MSFT,2,400.00,-800.00,\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        n = importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        assert n == 1

    def test_empty_csv_returns_zero(self, tmp_path):
        src = _write_tmp_csv(tmp_path, "vanguard_empty.csv", "")
        importer = VanguardImporter()
        n = importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        assert n == 0

    def test_multiple_transactions_all_written(self, tmp_path):
        content = (
            VANGUARD_TX_HEADER
            + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
            + "03/05/2026,Dividend,Vanguard Fund,VTI,0,0.00,25.00,25.00\n"
            + "03/10/2026,Sell,Microsoft Corp,MSFT,2,400.00,800.00,797.50\n"
        )
        src = _write_tmp_csv(tmp_path, "vanguard_tx.csv", content)
        importer = VanguardImporter()
        n = importer.import_transactions(str(src), "vanguard_001", str(tmp_path))
        assert n == 3


# ---------------------------------------------------------------------------
# VanguardImporter — import_auto mode detection
# ---------------------------------------------------------------------------


class TestVanguardImporterAuto:
    def test_auto_dispatches_to_transactions_when_trade_date_present(self, tmp_path):
        content = VANGUARD_TX_HEADER + "03/01/2026,Buy,Apple Inc,AAPL,5,150.00,-750.00,-750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_auto.csv", content)
        importer = VanguardImporter()
        n = importer.import_auto(str(src), "vanguard_001", str(tmp_path))
        assert n == 1
        assert (tmp_path / "transactions.csv").exists()
        assert not (tmp_path / "holdings.csv").exists()

    def test_auto_dispatches_to_holdings_when_symbol_present(self, tmp_path):
        content = VANGUARD_HOLDINGS_HEADER + "99999999,Brokerage,AAPL,Apple Inc,5,150.00,750.00\n"
        src = _write_tmp_csv(tmp_path, "vanguard_auto.csv", content)
        importer = VanguardImporter()
        n = importer.import_auto(str(src), "vanguard_001", str(tmp_path))
        assert n == 1
        assert (tmp_path / "holdings.csv").exists()
        assert not (tmp_path / "transactions.csv").exists()
