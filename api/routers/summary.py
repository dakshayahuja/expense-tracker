from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import Transaction, Category
from api.routers.transactions import _next_month

router = APIRouter(prefix="/api", tags=["summary"])

MONTHLY_INCOME_BASELINE = Decimal("107396")  # ₹1,08,896 gross − ₹1,500 insurance at source

LIFESTYLE_CATEGORIES = {
    "Housing", "Transport", "Food & Groceries",
    "Subscriptions & Entertainment", "Utilities", "Miscellaneous",
}


@router.get("/summary")
def get_summary(
    month: Optional[str] = Query(None, description="YYYY-MM, defaults to current month"),
    db: Session = Depends(get_db),
):
    if month:
        year, mon = map(int, month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month

    start = date(year, mon, 1)
    end = _next_month(year, mon)

    txns = (
        db.query(Transaction)
        .filter(Transaction.txn_date >= start, Transaction.txn_date < end)
        .all()
    )

    total_income = sum(t.amount for t in txns if t.type == "income")
    total_expense = sum(t.amount for t in txns if t.type == "expense")
    total_investment = sum(t.amount for t in txns if t.type == "investment")

    # Effective income: use actual recorded income or fall back to baseline
    effective_income = total_income if total_income > 0 else MONTHLY_INCOME_BASELINE

    # Category actuals
    category_actuals: dict[str, Decimal] = {}
    for txn in txns:
        if txn.type in ("expense", "investment"):
            category_actuals[txn.category] = (
                category_actuals.get(txn.category, Decimal("0")) + txn.amount
            )

    # Build per-category summary with budget data
    categories = db.query(Category).order_by(Category.sort_order).all()
    category_summary = []
    for cat in categories:
        actual = category_actuals.get(cat.name, Decimal("0"))

        # Insurance: always show as fully spent (pre-deducted)
        if cat.pre_deducted:
            actual = cat.monthly_budget

        budget = cat.monthly_budget
        pct = float(actual / budget * 100) if budget > 0 else 0

        category_summary.append({
            "name": cat.name,
            "type": cat.type,
            "pre_deducted": cat.pre_deducted,
            "budget": float(budget),
            "actual": float(actual),
            "remaining": float(budget - actual),
            "pct_used": round(pct, 1),
            "over_budget": actual > budget,
        })

    # Lifestyle spend (excludes insurance pre-deducted, investments)
    lifestyle_spend = sum(
        category_actuals.get(name, Decimal("0"))
        for name in LIFESTYLE_CATEGORIES
    )

    savings_rate = float((effective_income - lifestyle_spend) / effective_income * 100)

    return {
        "month": f"{year}-{mon:02d}",
        "total_income": float(effective_income),
        "total_expense": float(total_expense),
        "total_investment": float(total_investment),
        "net_saved": float(effective_income - total_expense - total_investment),
        "savings_rate": round(savings_rate, 1),
        "categories": category_summary,
    }


@router.get("/trends")
def get_trends(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    today = date.today()
    results = []

    for i in range(months - 1, -1, -1):
        mon = today.month - i
        year = today.year
        while mon <= 0:
            mon += 12
            year -= 1

        start = date(year, mon, 1)
        end = _next_month(year, mon)

        rows = (
            db.query(Transaction.category, func.sum(Transaction.amount).label("total"))
            .filter(Transaction.txn_date >= start, Transaction.txn_date < end)
            .filter(Transaction.type.in_(["expense", "investment"]))
            .group_by(Transaction.category)
            .all()
        )

        results.append({
            "month": f"{year}-{mon:02d}",
            "categories": {row.category: float(row.total) for row in rows},
        })

    return results
