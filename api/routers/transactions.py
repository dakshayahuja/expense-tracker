import io
import csv
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from api.database import get_db
from api.models import Transaction
from api.schemas import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)

    if month:
        try:
            year, mon = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="month must be YYYY-MM")
        q = q.filter(
            Transaction.txn_date >= date(year, mon, 1),
            Transaction.txn_date < _next_month(year, mon),
        )

    if category:
        q = q.filter(Transaction.category == category)

    if type:
        q = q.filter(Transaction.type == type)

    return q.order_by(Transaction.txn_date.desc(), Transaction.created_at.desc()).all()


@router.get("/export")
def export_transactions_csv(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    q = db.query(Transaction)
    if month:
        try:
            year, mon = map(int, month.split("-"))
        except ValueError:
            raise HTTPException(status_code=400, detail="month must be YYYY-MM")
        q = q.filter(
            Transaction.txn_date >= date(year, mon, 1),
            Transaction.txn_date < _next_month(year, mon),
        )
    txns = q.order_by(Transaction.txn_date.asc(), Transaction.created_at.asc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Description", "Subcategory", "Category", "Type", "Amount", "Account", "Source"])
    for t in txns:
        writer.writerow([
            t.txn_date, t.description or "", t.subcategory or "",
            t.category, t.type, t.amount, t.account or "", t.source,
        ])
    content = buf.getvalue().encode("utf-8")
    filename = f"expenses_{month or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/bulk", status_code=201)
def bulk_create_transactions(payload: List[TransactionCreate], db: Session = Depends(get_db)):
    txns = [Transaction(**t.model_dump()) for t in payload]
    db.add_all(txns)
    db.commit()
    return {"imported": len(txns)}


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    txn = Transaction(**payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.put("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.id == txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(txn)
    db.commit()


def _next_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)
