from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator


class CategoryBase(BaseModel):
    name: str
    monthly_budget: Decimal
    type: str
    pre_deducted: bool = False
    keywords: str = ""
    sort_order: int = 99


class CategoryCreate(CategoryBase):
    pass


class CategoryOut(CategoryBase):
    id: int

    model_config = {"from_attributes": True}


class TransactionBase(BaseModel):
    amount: Decimal
    type: str
    category: str
    subcategory: str = ""
    description: str = ""
    txn_date: date
    source: str = "web"
    account: str = ""

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"expense", "income", "investment"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = None
    type: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    txn_date: Optional[date] = None
    account: Optional[str] = None


class TransactionOut(TransactionBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
