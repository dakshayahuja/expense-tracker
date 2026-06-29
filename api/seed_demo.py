"""
Seed demo transactions for testing the dashboard.
Run: python -m api.seed_demo
"""
import sys, os, random
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Transaction

DEMO = [
    # June 2026 - current month
    (21000, "expense", "Housing", "Rent", "rent june", date(2026, 6, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture installment", date(2026, 6, 1)),
    (9000, "expense", "Transport", "Fuel", "monthly fuel", date(2026, 6, 3)),
    (15000, "expense", "Transport", "Car repayment", "car repayment parents", date(2026, 6, 1)),
    (800, "expense", "Food & Groceries", "Dining out", "zomato", date(2026, 6, 5)),
    (2400, "expense", "Food & Groceries", "Groceries", "blinkit groceries", date(2026, 6, 7)),
    (650, "expense", "Food & Groceries", "Dining out", "restaurant dinner", date(2026, 6, 12)),
    (3200, "expense", "Food & Groceries", "Groceries", "zepto monthly", date(2026, 6, 15)),
    (1800, "expense", "Food & Groceries", "Dining out", "swiggy lunch x6", date(2026, 6, 20)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "netflix spotify prime", date(2026, 6, 5)),
    (1200, "expense", "Subscriptions & Entertainment", "Movie", "movie + popcorn", date(2026, 6, 18)),
    (1800, "expense", "Utilities", "Bills", "electricity wifi phone", date(2026, 6, 10)),
    (900, "expense", "Utilities", "Gas", "lpg refill", date(2026, 6, 14)),
    (2200, "expense", "Miscellaneous", "Clothes", "amazon shopping", date(2026, 6, 8)),
    (800, "expense", "Miscellaneous", "Haircut", "salon haircut", date(2026, 6, 22)),
    (10000, "investment", "Investments/SIP", "", "SIP june", date(2026, 6, 5)),
    (10000, "investment", "Emergency Fund", "", "AU bank transfer", date(2026, 6, 5)),
    (3000, "investment", "Stocks/IPO", "", "yes bank top-up", date(2026, 6, 10)),
    (107396, "income", "Housing", "", "June salary", date(2026, 6, 1)),

    # May 2026
    (21000, "expense", "Housing", "Rent", "rent may", date(2026, 5, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture installment", date(2026, 5, 1)),
    (9200, "expense", "Transport", "Fuel", "petrol", date(2026, 5, 4)),
    (15000, "expense", "Transport", "Car repayment", "car parents", date(2026, 5, 1)),
    (4100, "expense", "Food & Groceries", "Groceries", "blinkit+zepto", date(2026, 5, 10)),
    (6200, "expense", "Food & Groceries", "Dining out", "restaurants+swiggy", date(2026, 5, 20)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "subscriptions", date(2026, 5, 5)),
    (2400, "expense", "Utilities", "Bills", "bills", date(2026, 5, 8)),
    (3100, "expense", "Miscellaneous", "Shopping", "clothes+gifts", date(2026, 5, 15)),
    (10000, "investment", "Investments/SIP", "", "SIP may", date(2026, 5, 5)),
    (10000, "investment", "Emergency Fund", "", "AU bank", date(2026, 5, 5)),

    # April 2026
    (21000, "expense", "Housing", "Rent", "rent apr", date(2026, 4, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture", date(2026, 4, 1)),
    (8800, "expense", "Transport", "Fuel", "fuel", date(2026, 4, 3)),
    (10000, "expense", "Transport", "Car repayment", "car parents", date(2026, 4, 1)),
    (3800, "expense", "Food & Groceries", "Groceries", "groceries", date(2026, 4, 12)),
    (4900, "expense", "Food & Groceries", "Dining out", "dining", date(2026, 4, 22)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "subs", date(2026, 4, 5)),
    (2100, "expense", "Utilities", "Bills", "bills", date(2026, 4, 8)),
    (1800, "expense", "Miscellaneous", "Misc", "misc", date(2026, 4, 18)),
    (10000, "investment", "Investments/SIP", "", "SIP apr", date(2026, 4, 5)),

    # March 2026
    (21000, "expense", "Housing", "Rent", "rent mar", date(2026, 3, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture", date(2026, 3, 1)),
    (9500, "expense", "Transport", "Fuel", "fuel", date(2026, 3, 3)),
    (20000, "expense", "Transport", "Car repayment", "car parents (higher)", date(2026, 3, 1)),
    (5200, "expense", "Food & Groceries", "Groceries", "groceries", date(2026, 3, 12)),
    (7100, "expense", "Food & Groceries", "Dining out", "dining hot month", date(2026, 3, 22)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "subs", date(2026, 3, 5)),
    (2600, "expense", "Utilities", "Bills", "bills", date(2026, 3, 8)),
    (4200, "expense", "Miscellaneous", "Misc", "misc+gifts", date(2026, 3, 18)),
    (10000, "investment", "Investments/SIP", "", "SIP mar", date(2026, 3, 5)),

    # February 2026
    (21000, "expense", "Housing", "Rent", "rent feb", date(2026, 2, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture", date(2026, 2, 1)),
    (8600, "expense", "Transport", "Fuel", "fuel", date(2026, 2, 3)),
    (15000, "expense", "Transport", "Car repayment", "car parents", date(2026, 2, 1)),
    (3900, "expense", "Food & Groceries", "Groceries", "groceries", date(2026, 2, 12)),
    (5600, "expense", "Food & Groceries", "Dining out", "dining", date(2026, 2, 22)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "subs", date(2026, 2, 5)),
    (2200, "expense", "Utilities", "Bills", "bills", date(2026, 2, 8)),
    (2900, "expense", "Miscellaneous", "Misc", "misc", date(2026, 2, 18)),
    (10000, "investment", "Investments/SIP", "", "SIP feb", date(2026, 2, 5)),

    # January 2026
    (21000, "expense", "Housing", "Rent", "rent jan", date(2026, 1, 1)),
    (5500, "expense", "Housing", "Furniture", "furniture", date(2026, 1, 1)),
    (9100, "expense", "Transport", "Fuel", "fuel", date(2026, 1, 3)),
    (15000, "expense", "Transport", "Car repayment", "car parents", date(2026, 1, 1)),
    (4300, "expense", "Food & Groceries", "Groceries", "groceries", date(2026, 1, 12)),
    (6800, "expense", "Food & Groceries", "Dining out", "dining out lots", date(2026, 1, 22)),
    (2100, "expense", "Subscriptions & Entertainment", "OTT", "subs", date(2026, 1, 5)),
    (2400, "expense", "Utilities", "Bills", "bills", date(2026, 1, 8)),
    (3500, "expense", "Miscellaneous", "Misc", "misc", date(2026, 1, 18)),
    (10000, "investment", "Investments/SIP", "", "SIP jan", date(2026, 1, 5)),
]


def seed_demo():
    db = SessionLocal()
    try:
        existing = db.query(Transaction).count()
        if existing > 2:
            print(f"Transactions already exist ({existing}). Skipping demo seed.")
            return
        for row in DEMO:
            amount, txn_type, category, subcategory, description, txn_date = row
            db.add(Transaction(
                amount=amount,
                type=txn_type,
                category=category,
                subcategory=subcategory,
                description=description,
                txn_date=txn_date,
                source="web",
            ))
        db.commit()
        print(f"Seeded {len(DEMO)} demo transactions.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo()
