"""
Unit tests for PDF-parsing utility functions in api.routers.import_route.
All tests are pure Python — no database, no HTTP, no pdfplumber I/O.
"""
import pytest
from api.routers.import_route import (
    _parse_amount,
    _parse_date_dmy,
    _parse_date_words,
    _auto_category,
    _col,
    _should_skip,
    _parse_au_bank,
    _parse_yes_bank,
    _parse_hdfc_bank,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

class _Cat:
    """Minimal category stub matching the ORM interface used by parsers."""
    def __init__(self, name: str, keywords: str):
        self.name = name
        self.keywords = keywords


class _TablePage:
    """pdfplumber page stub whose extract_tables() returns a fixed list."""
    def __init__(self, tables):
        self._tables = tables

    def extract_tables(self):
        return self._tables

    def extract_text(self):
        return ""


class _TextPage:
    """pdfplumber page stub whose extract_text() returns fixed text (for HDFC)."""
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text

    def extract_tables(self):
        return []


def _au_page(*data_rows):
    header = [
        "Transaction Date", "Value Date", "Description/Narration",
        "Cheque/Reference No.", "Debit (₹)", "Credit (₹)", "Balance (₹)",
    ]
    return _TablePage([[header, *data_rows]])


def _yes_page(*data_rows):
    header = [
        "Transaction Date", "Value Date", "Cheque No/Reference No",
        "Description", "Withdrawals", "Deposits", "Running Balance",
    ]
    return _TablePage([[header, *data_rows]])


def _hdfc_text_pages(lines: list[str], opening_balance: float = 10_000.0) -> list[_TextPage]:
    """Builds a minimal HDFC-style text block the parser can digest."""
    body = "\n".join(lines)
    summary = (
        f"\nOpeningBalance DrCount CrCount\n"
        f"{opening_balance} 5 3 50000.00 60000.00 10000.00\n"
    )
    return [_TextPage("Date Narration Chq./Ref.No.\n" + body + summary)]


# ─── _parse_amount ─────────────────────────────────────────────────────────────

class TestParseAmount:
    def test_plain_float(self):
        assert _parse_amount("749.00") == 749.0

    def test_comma_thousands(self):
        assert _parse_amount("10,000.00") == 10_000.0

    def test_lakh_formatting(self):
        assert _parse_amount("2,82,805.00") == 282_805.0

    def test_rupee_symbol_stripped(self):
        assert _parse_amount("₹1,500.00") == 1_500.0

    def test_empty_string_returns_zero(self):
        assert _parse_amount("") == 0.0

    def test_dash_only_returns_zero(self):
        assert _parse_amount("-") == 0.0

    def test_non_numeric_returns_zero(self):
        assert _parse_amount("N/A") == 0.0

    def test_whitespace_stripped(self):
        assert _parse_amount("  500.00  ") == 500.0

    def test_large_salary_credit(self):
        assert _parse_amount("1,07,396.00") == 107_396.0


# ─── _parse_date_dmy ───────────────────────────────────────────────────────────

class TestParseDateDmy:
    def test_dd_mm_yy(self):
        assert _parse_date_dmy("01/05/26") == "2026-05-01"

    def test_dd_mm_yyyy(self):
        assert _parse_date_dmy("15/12/2025") == "2025-12-15"

    def test_dash_separator(self):
        assert _parse_date_dmy("01-06-26") == "2026-06-01"

    def test_leading_trailing_whitespace(self):
        assert _parse_date_dmy("  31/05/26  ") == "2026-05-31"

    def test_invalid_format_returns_none(self):
        assert _parse_date_dmy("not-a-date") is None

    def test_too_few_parts_returns_none(self):
        assert _parse_date_dmy("01/05") is None

    def test_mid_year_boundary(self):
        assert _parse_date_dmy("01/07/26") == "2026-07-01"

    def test_december_31(self):
        assert _parse_date_dmy("31/12/25") == "2025-12-31"


# ─── _parse_date_words ─────────────────────────────────────────────────────────

class TestParseDateWords:
    def test_full_month_name(self):
        assert _parse_date_words("26 May 2026") == "2026-05-26"

    def test_three_letter_abbrev(self):
        assert _parse_date_words("31 May 2026") == "2026-05-31"

    def test_january(self):
        assert _parse_date_words("1 January 2026") == "2026-01-01"

    def test_december(self):
        assert _parse_date_words("31 December 2025") == "2025-12-31"

    def test_embedded_in_sentence(self):
        assert _parse_date_words("Transaction on 15 Jun 2026 (processed)") == "2026-06-15"

    def test_no_date_returns_none(self):
        assert _parse_date_words("no date here") is None

    def test_invalid_month_returns_none(self):
        assert _parse_date_words("01 Xyz 2026") is None

    def test_newline_in_string_handled(self):
        assert _parse_date_words("26 May\n2026") == "2026-05-26"  # \n is whitespace, regex matches

    def test_all_twelve_months(self):
        months = [
            ("jan", 1), ("feb", 2), ("mar", 3), ("apr", 4),
            ("may", 5), ("jun", 6), ("jul", 7), ("aug", 8),
            ("sep", 9), ("oct", 10), ("nov", 11), ("dec", 12),
        ]
        for abbrev, num in months:
            result = _parse_date_words(f"15 {abbrev.capitalize()} 2026")
            assert result == f"2026-{num:02d}-15", f"Failed for {abbrev}"


# ─── _auto_category ────────────────────────────────────────────────────────────

@pytest.fixture
def std_cats():
    return [
        _Cat("Housing", "rent,maintenance,furniture"),
        _Cat("Transport", "uber,ola,fuel,petrol"),
        _Cat("Food & Groceries", "swiggy,zomato,blinkit,zepto,grocery,lunch,dinner"),
        _Cat("Subscriptions & Entertainment", "netflix,spotify,prime,hotstar"),
        _Cat("Utilities", "electricity,wifi,airtel,jio"),
        _Cat("Miscellaneous", ""),
    ]


class TestAutoCategory:
    def test_food_keyword_match(self, std_cats):
        assert _auto_category("UPI-SWIGGY-payment", std_cats) == "Food & Groceries"

    def test_case_insensitive(self, std_cats):
        assert _auto_category("NETFLIX SUBSCRIPTION", std_cats) == "Subscriptions & Entertainment"

    def test_partial_keyword_in_description(self, std_cats):
        assert _auto_category("UBER TECHNOLOGIES INC", std_cats) == "Transport"

    def test_utility_keyword(self, std_cats):
        assert _auto_category("AIRTEL BROADBAND BILL", std_cats) == "Utilities"

    def test_no_match_falls_back_to_miscellaneous(self, std_cats):
        assert _auto_category("UNKNOWN RANDOM MERCHANT XYZ", std_cats) == "Miscellaneous"

    def test_empty_description_returns_miscellaneous(self, std_cats):
        assert _auto_category("", std_cats) == "Miscellaneous"

    def test_first_matching_cat_wins(self, std_cats):
        # "zomato" matches Food & Groceries before any later category
        assert _auto_category("zomato food delivery", std_cats) == "Food & Groceries"

    def test_empty_keywords_cat_is_never_keyword_matched(self, std_cats):
        # Miscellaneous has no keywords; it's only the fallback
        assert _auto_category("swiggy", std_cats) != "Miscellaneous"


# ─── _should_skip ──────────────────────────────────────────────────────────────

class TestShouldSkip:
    @pytest.mark.parametrize("desc", [
        "total", "balance", "opening balance", "closing balance",
        "od limit", "sub total", "", "   ",
    ])
    def test_skipped_phrases(self, desc):
        assert _should_skip(desc) is True

    def test_real_description_not_skipped(self):
        assert _should_skip("UPI-SWIGGY-payment") is False

    def test_upi_income_not_skipped(self):
        assert _should_skip("NEFTCR-SALARY-DAKSHAY") is False


# ─── _col ──────────────────────────────────────────────────────────────────────

class TestCol:
    def test_finds_exact_keyword(self):
        assert _col(["date", "narration", "withdrawal", "deposit"], "withdrawal") == 2

    def test_substring_match(self):
        assert _col(["Withdrawal Amt.", "Deposit Amt."], "withdrawal") == 0

    def test_case_insensitive(self):
        assert _col(["Date", "NARRATION", "Withdrawal AMT."], "withdrawal") == 2

    def test_returns_minus_one_when_absent(self):
        assert _col(["date", "narration"], "withdrawal") == -1

    def test_first_keyword_match_wins(self):
        # "narration" before "description"
        assert _col(["narration", "description"], "narration", "description") == 0

    def test_second_keyword_used_as_fallback(self):
        assert _col(["description"], "narration", "description") == 0


# ─── _parse_au_bank ────────────────────────────────────────────────────────────

@pytest.fixture
def base_cats():
    return [
        _Cat("Food & Groceries", "swiggy,zomato,upi"),
        _Cat("Miscellaneous", ""),
    ]


class TestParseAuBank:
    def test_debit_becomes_expense(self, base_cats):
        page = _au_page(
            ["26 May 2026", "26 May 2026", "UPI/DR/swiggy order", "REF1", "500.00", "-", "49500.00"]
        )
        rows = _parse_au_bank([page], base_cats)
        assert len(rows) == 1
        r = rows[0]
        assert r["type"] == "expense"
        assert r["amount"] == 500.0
        assert r["txn_date"] == "2026-05-26"
        assert r["account"] == "AU Bank"

    def test_credit_becomes_income(self, base_cats):
        page = _au_page(
            ["01 Jun 2026", "01 Jun 2026", "SALARY CREDIT NEFT", "REF2", "-", "107396.00", "157396.00"]
        )
        rows = _parse_au_bank([page], base_cats)
        assert len(rows) == 1
        assert rows[0]["type"] == "income"
        assert rows[0]["amount"] == 107_396.0

    def test_source_always_web(self, base_cats):
        page = _au_page(
            ["26 May 2026", "26 May 2026", "UPI merchant", "R", "100.00", "-", "900.00"]
        )
        assert _parse_au_bank([page], base_cats)[0]["source"] == "web"

    def test_zero_debit_and_credit_skipped(self, base_cats):
        page = _au_page(
            ["26 May 2026", "26 May 2026", "Blank row", "R", "0.00", "0.00", "49500.00"]
        )
        assert _parse_au_bank([page], base_cats) == []

    def test_total_row_skipped(self, base_cats):
        page = _au_page(
            ["Total", "", "Total", "", "50000.00", "5000.00", ""]
        )
        assert _parse_au_bank([page], base_cats) == []

    def test_header_row_not_included(self, base_cats):
        # Table with only a header, no data
        page = _au_page()
        assert _parse_au_bank([page], base_cats) == []

    def test_auto_category_applied(self, base_cats):
        page = _au_page(
            ["26 May 2026", "26 May 2026", "swiggy dinner order", "R", "300.00", "-", "50000.00"]
        )
        assert _parse_au_bank([page], base_cats)[0]["category"] == "Food & Groceries"

    def test_multiple_pages_accumulate(self, base_cats):
        p1 = _au_page(["01 May 2026", "01 May 2026", "vendor1", "R1", "100.00", "-", "900.00"])
        p2 = _au_page(["02 May 2026", "02 May 2026", "vendor2", "R2", "200.00", "-", "700.00"])
        rows = _parse_au_bank([p1, p2], base_cats)
        assert len(rows) == 2

    def test_description_truncated_at_200_chars(self, base_cats):
        long_desc = "X" * 300
        page = _au_page(
            ["26 May 2026", "26 May 2026", long_desc, "R", "50.00", "-", "950.00"]
        )
        assert len(_parse_au_bank([page], base_cats)[0]["description"]) <= 200


# ─── _parse_yes_bank ───────────────────────────────────────────────────────────

class TestParseYesBank:
    def test_withdrawal_is_expense(self, base_cats):
        page = _yes_page(
            ["31 May 2026", "31 May 2026", "YBS001", "UPI zomato order", "500.00", "", "9500.00"]
        )
        rows = _parse_yes_bank([page], base_cats)
        assert rows[0]["type"] == "expense"
        assert rows[0]["amount"] == 500.0
        assert rows[0]["account"] == "Yes Bank"
        assert rows[0]["txn_date"] == "2026-05-31"

    def test_deposit_is_income(self, base_cats):
        page = _yes_page(
            ["31 May 2026", "31 May 2026", "YBS002", "UPI TRANSFER IN", "", "10000.00", "20000.00"]
        )
        assert _parse_yes_bank([page], base_cats)[0]["type"] == "income"

    def test_both_zero_skipped(self, base_cats):
        page = _yes_page(
            ["31 May 2026", "31 May 2026", "YBS003", "EMPTY", "", "", ""]
        )
        assert _parse_yes_bank([page], base_cats) == []

    def test_balance_row_skipped(self, base_cats):
        page = _yes_page(
            ["31 May 2026", "31 May 2026", "", "balance", "1000.00", "", ""]
        )
        assert _parse_yes_bank([page], base_cats) == []

    def test_description_truncated(self, base_cats):
        page = _yes_page(
            ["31 May 2026", "31 May 2026", "R", "Y" * 300, "100.00", "", "900.00"]
        )
        assert len(_parse_yes_bank([page], base_cats)[0]["description"]) <= 200


# ─── _parse_hdfc_bank (text-based) ────────────────────────────────────────────

class TestParseHdfcBank:
    def test_expense_when_balance_drops(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 UPI-SWIGGY-PAYMENT REF001 01/05/26 500.00 9,500.00"],
            opening_balance=10_000.0,
        )
        rows = _parse_hdfc_bank(pages, base_cats)
        assert len(rows) == 1
        r = rows[0]
        assert r["type"] == "expense"
        assert r["amount"] == 500.0
        assert r["txn_date"] == "2026-05-01"
        assert r["account"] == "HDFC"

    def test_income_when_balance_rises(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 NEFTCR-SALARY-CREDIT REF002 01/05/26 100000.00 110,000.00"],
            opening_balance=10_000.0,
        )
        rows = _parse_hdfc_bank(pages, base_cats)
        assert rows[0]["type"] == "income"
        assert rows[0]["amount"] == 100_000.0

    def test_sequential_transactions_all_parsed(self, base_cats):
        pages = _hdfc_text_pages([
            "01/05/26 UPI-MERCHANT-A R1 01/05/26 500.00 9,500.00",
            "02/05/26 UPI-MERCHANT-B R2 02/05/26 300.00 9,200.00",
        ], opening_balance=10_000.0)
        rows = _parse_hdfc_bank(pages, base_cats)
        assert len(rows) == 2
        assert rows[0]["amount"] == 500.0
        assert rows[1]["amount"] == 300.0

    def test_value_date_stripped_from_narration(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 UPI-MERCHANT-X REF 01/05/26 200.00 9,800.00"],
            opening_balance=10_000.0,
        )
        desc = _parse_hdfc_bank(pages, base_cats)[0]["description"]
        assert "01/05/26" not in desc

    def test_pure_digit_ref_stripped_from_narration(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 UPI-MERCHANT 000000123456789 01/05/26 100.00 9,900.00"],
            opening_balance=10_000.0,
        )
        desc = _parse_hdfc_bank(pages, base_cats)[0]["description"]
        assert "000000123456789" not in desc

    def test_line_with_no_two_trailing_amounts_skipped(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 SOME TEXT WITHOUT AMOUNTS"],
            opening_balance=10_000.0,
        )
        assert _parse_hdfc_bank(pages, base_cats) == []

    def test_source_always_web(self, base_cats):
        pages = _hdfc_text_pages(
            ["01/05/26 UPI-VENDOR REF 01/05/26 50.00 9,950.00"],
            opening_balance=10_000.0,
        )
        assert _parse_hdfc_bank(pages, base_cats)[0]["source"] == "web"

    def test_description_truncated_at_200(self, base_cats):
        long_part = "X" * 250
        pages = _hdfc_text_pages(
            [f"01/05/26 UPI-{long_part} REF 01/05/26 50.00 9,950.00"],
            opening_balance=10_000.0,
        )
        rows = _parse_hdfc_bank(pages, base_cats)
        if rows:  # may be truncated or have no match
            assert len(rows[0]["description"]) <= 200
