import io
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Category

router = APIRouter(prefix="/api/import", tags=["import"])

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

VALID_BANKS = {"au", "yes", "hdfc"}
BANK_LABELS = {"au": "AU Bank", "yes": "Yes Bank", "hdfc": "HDFC"}


def _parse_amount(s: str) -> float:
    if not s:
        return 0.0
    cleaned = re.sub(r"[₹,\s]", "", str(s)).strip("-")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_date_dmy(raw: str) -> Optional[str]:
    """DD/MM/YY or DD/MM/YYYY → YYYY-MM-DD"""
    raw = re.sub(r"\s+", "", str(raw).strip())
    parts = re.split(r"[/\-]", raw)
    if len(parts) != 3:
        return None
    dd, mm, yy = parts
    if len(yy) == 2:
        yy = "20" + yy
    try:
        return f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}"
    except ValueError:
        return None


def _parse_date_words(raw: str) -> Optional[str]:
    """DD Mon YYYY → YYYY-MM-DD (e.g. '26 May 2026')"""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", str(raw).replace("\n", " "))
    if not m:
        return None
    dd, mon, yyyy = m.group(1), m.group(2).lower()[:3], m.group(3)
    month_num = MONTH_MAP.get(mon)
    if not month_num:
        return None
    try:
        return f"{int(yyyy):04d}-{month_num:02d}-{int(dd):02d}"
    except ValueError:
        return None


def _col(headers: list, *keywords) -> int:
    for i, h in enumerate(headers):
        hl = str(h or "").lower()
        for kw in keywords:
            if kw.lower() in hl:
                return i
    return -1


def _auto_category(description: str, cats: list) -> str:
    desc = str(description).lower()
    for cat in cats:
        if not cat.keywords:
            continue
        for kw in cat.keywords.split(","):
            kw = kw.strip().lower()
            if kw and kw in desc:
                return cat.name
    return "Miscellaneous"


def _cell(row: list, idx: int) -> str:
    if idx < 0 or idx >= len(row):
        return ""
    return str(row[idx] or "").strip().replace("\n", " ")


SKIP_PHRASES = {"total", "balance", "opening balance", "closing balance", "od limit", "sub total"}


def _should_skip(desc: str) -> bool:
    return desc.lower().strip() in SKIP_PHRASES or not desc.strip()


# ── AU Bank ──────────────────────────────────────────────────────────────────
# Table format: Transaction Date | Value Date | Description/Narration |
#               Cheque/Ref | Debit (₹) | Credit (₹) | Balance (₹)
def _parse_au_bank(pages, cats: list) -> list:
    rows = []
    for page in pages:
        for table in (page.extract_tables() or []):
            if not table:
                continue
            hi = next(
                (i for i, r in enumerate(table) if r and any("date" in str(c or "").lower() for c in r)),
                0
            )
            headers = [str(c or "").lower() for c in table[hi]]
            date_col  = _col(headers, "transaction date", "trans date", "date") or 0
            desc_col  = _col(headers, "narration", "description") if _col(headers, "narration", "description") >= 0 else 2
            debit_col = _col(headers, "debit") if _col(headers, "debit") >= 0 else 4
            cred_col  = _col(headers, "credit") if _col(headers, "credit") >= 0 else 5

            for row in table[hi + 1:]:
                if not row or len(row) < 5:
                    continue
                desc = _cell(row, desc_col)
                if _should_skip(desc):
                    continue
                txn_date = _parse_date_words(_cell(row, date_col))
                if not txn_date:
                    continue
                debit  = _parse_amount(_cell(row, debit_col))
                credit = _parse_amount(_cell(row, cred_col))
                if debit == 0 and credit == 0:
                    continue
                rows.append({
                    "txn_date": txn_date,
                    "description": desc[:200],
                    "category": _auto_category(desc, cats),
                    "type": "expense" if debit > 0 else "income",
                    "amount": round(debit if debit > 0 else credit, 2),
                    "source": "web",
                    "subcategory": "",
                    "account": "AU Bank",
                })
    return rows


# ── Yes Bank ─────────────────────────────────────────────────────────────────
# Table: Transaction Date | Value Date | Cheque No/Ref | Description |
#        Withdrawals | Deposits | Running Balance
def _parse_yes_bank(pages, cats: list) -> list:
    rows = []
    for page in pages:
        for table in (page.extract_tables() or []):
            if not table:
                continue
            hi = next(
                (i for i, r in enumerate(table) if r and any("date" in str(c or "").lower() for c in r)),
                0
            )
            headers = [str(c or "").lower() for c in table[hi]]
            date_col = _col(headers, "transaction date", "date") if _col(headers, "transaction date", "date") >= 0 else 0
            desc_col = _col(headers, "description", "narration", "remarks") if _col(headers, "description", "narration", "remarks") >= 0 else 3
            with_col = _col(headers, "withdrawal", "debit") if _col(headers, "withdrawal", "debit") >= 0 else 4
            dep_col  = _col(headers, "deposit", "credit") if _col(headers, "deposit", "credit") >= 0 else 5

            for row in table[hi + 1:]:
                if not row or len(row) < 5:
                    continue
                desc = _cell(row, desc_col)
                if _should_skip(desc):
                    continue
                txn_date = _parse_date_words(_cell(row, date_col))
                if not txn_date:
                    continue
                withdrawal = _parse_amount(_cell(row, with_col))
                deposit    = _parse_amount(_cell(row, dep_col))
                if withdrawal == 0 and deposit == 0:
                    continue
                rows.append({
                    "txn_date": txn_date,
                    "description": desc[:200],
                    "category": _auto_category(desc, cats),
                    "type": "expense" if withdrawal > 0 else "income",
                    "amount": round(withdrawal if withdrawal > 0 else deposit, 2),
                    "source": "web",
                    "subcategory": "",
                    "account": "Yes Bank",
                })
    return rows


# ── HDFC Bank ────────────────────────────────────────────────────────────────
# Table: Date | Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. |
#        Deposit Amt. | Closing Balance
#
# HDFC PDFs have no horizontal row borders, so pdfplumber collapses every
# transaction into a single table cell (all dates joined by \n, all narrations
# joined by \n, etc.). Text extraction is far more reliable: each transaction
# appears on its own text line starting with DD/MM/YY.
# Balance-delta determines expense vs income without needing column positions.
def _parse_hdfc_bank(pages, cats: list) -> list:
    full_text = "\n".join(page.extract_text() or "" for page in pages)

    # Opening balance from statement summary (to anchor the first delta)
    ob_m = re.search(
        r"(?:Opening|Open)\s*Bal(?:ance)?[\s\S]{0,60}?(\d[\d,]*\.\d{2})",
        full_text, re.IGNORECASE
    )
    prev_balance: Optional[float] = _parse_amount(ob_m.group(1)) if ob_m else None

    # Each transaction line starts with DD/MM/YY at column 0
    DATE_LINE = re.compile(r"^(\d{2}/\d{2}/\d{2})\b", re.MULTILINE)
    AMOUNTS_END = re.compile(r"([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$")

    matches = list(DATE_LINE.finditer(full_text))
    rows = []

    for i, m in enumerate(matches):
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        first_line = full_text[m.start():block_end].split("\n")[0].strip()

        txn_date = _parse_date_dmy(m.group(1))
        if not txn_date:
            continue

        # Last two numbers on the line: [txn_amount, closing_balance]
        am = AMOUNTS_END.search(first_line)
        if not am:
            continue

        txn_amount = _parse_amount(am.group(1))
        closing    = _parse_amount(am.group(2))
        if txn_amount == 0:
            continue

        # Determine direction from balance delta
        if prev_balance is not None:
            delta = closing - prev_balance
            txn_type = "income" if delta > 0 else "expense"
        else:
            # No opening balance; fall back to second-to-last amount sign
            txn_type = "income"  # first line in an HDFC statement is usually the salary credit

        prev_balance = closing

        # Narration: use first line only (continuation lines in HDFC text mix
        # narration overflow with amount values from adjacent columns).
        desc = first_line[8:].strip()                                       # remove leading DD/MM/YY
        desc = re.sub(r"\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s*$", "", desc)  # strip trailing amounts
        desc = re.sub(r"\s+\d{2}/\d{2}/\d{2}(?=\s|$)", "", desc)          # strip value date
        desc = re.sub(r"\b\d{12,}\b", "", desc)                            # strip long numeric refs
        desc = " ".join(desc.split())

        if not desc or _should_skip(desc):
            continue

        rows.append({
            "txn_date": txn_date,
            "description": desc[:200],
            "category": _auto_category(desc, cats),
            "type": txn_type,
            "amount": round(txn_amount, 2),
            "source": "web",
            "subcategory": "",
            "account": "HDFC",
        })

    return rows


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/parse")
async def parse_statement(
    file: UploadFile = File(...),
    bank: str = Form(...),
    db: Session = Depends(get_db),
):
    """Parse a PDF bank statement. `bank` must be one of: au, yes, hdfc."""
    if bank not in VALID_BANKS:
        raise HTTPException(400, f"bank must be one of: {', '.join(VALID_BANKS)}")

    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(500, "pdfplumber not installed — run: pip install pdfplumber")

    fname = (file.filename or "").lower()
    if not fname.endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF file (.pdf)")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10 MB)")

    cats = db.query(Category).all()

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            if bank == "au":
                rows = _parse_au_bank(pdf.pages, cats)
            elif bank == "yes":
                rows = _parse_yes_bank(pdf.pages, cats)
            else:  # hdfc
                rows = _parse_hdfc_bank(pdf.pages, cats)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not parse PDF: {e}")

    if not rows:
        raise HTTPException(
            400,
            f"No transactions found in {BANK_LABELS[bank]} statement. "
            "The PDF may be image-scanned or have an unsupported layout."
        )

    return {"rows": rows, "count": len(rows), "bank": bank}
