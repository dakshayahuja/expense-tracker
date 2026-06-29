from datetime import date, datetime
from sqlalchemy import Column, Integer, Numeric, Text, Boolean, Date, DateTime, func
from api.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, unique=True, nullable=False)
    monthly_budget = Column(Numeric(12, 2), nullable=False, default=0)
    type = Column(Text, nullable=False)  # expense | investment | income | structural
    pre_deducted = Column(Boolean, default=False)
    keywords = Column(Text, default="")  # comma-separated, used by Telegram parser
    sort_order = Column(Integer, default=99)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    type = Column(Text, nullable=False)  # expense | income | investment
    category = Column(Text, nullable=False)
    subcategory = Column(Text, default="")
    description = Column(Text, default="")
    txn_date = Column(Date, default=date.today)
    source = Column(Text, default="web")  # web | telegram
    account = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
