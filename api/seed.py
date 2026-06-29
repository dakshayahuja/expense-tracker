"""
Seed categories and budget data from the brief.
Run once after migration: python -m api.seed
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal, engine, Base
from api.models import Category

CATEGORIES = [
    {
        "name": "Housing",
        "monthly_budget": 26500,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "rent,maintenance,furniture,installment,society",
        "sort_order": 1,
    },
    {
        "name": "Transport",
        "monthly_budget": 24000,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "fuel,petrol,car,uber,ola,auto,metro,bus,parking,toll,rapido",
        "sort_order": 2,
    },
    {
        "name": "Food & Groceries",
        "monthly_budget": 15000,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "lunch,dinner,breakfast,swiggy,zomato,groceries,blinkit,zepto,restaurant,cafe,coffee,tea,food,snack,bigbasket,dunzo",
        "sort_order": 3,
    },
    {
        "name": "Subscriptions & Entertainment",
        "monthly_budget": 10000,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "netflix,hotstar,spotify,prime,youtube,subscription,movie,theatre,concert,game,steam,apple",
        "sort_order": 4,
    },
    {
        "name": "Utilities",
        "monthly_budget": 5000,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "electricity,water,wifi,internet,phone,mobile,recharge,gas,lpg,bill",
        "sort_order": 5,
    },
    {
        "name": "Miscellaneous",
        "monthly_budget": 5000,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "clothes,gift,shopping,amazon,flipkart,haircut,salon,medical,medicine,doctor,pharmacy",
        "sort_order": 6,
    },
    {
        "name": "Insurance",
        "monthly_budget": 1500,
        "type": "structural",
        "pre_deducted": True,
        "keywords": "insurance",
        "sort_order": 7,
    },
    {
        "name": "Investments/SIP",
        "monthly_budget": 10000,
        "type": "investment",
        "pre_deducted": False,
        "keywords": "sip,mutual fund,investment,zerodha,groww,kuvera",
        "sort_order": 8,
    },
    {
        "name": "Emergency Fund",
        "monthly_budget": 10000,
        "type": "investment",
        "pre_deducted": False,
        "keywords": "emergency,au bank,savings",
        "sort_order": 9,
    },
    {
        "name": "Stocks/IPO",
        "monthly_budget": 3000,
        "type": "investment",
        "pre_deducted": False,
        "keywords": "stocks,ipo,shares,yes bank,equity,nse,bse",
        "sort_order": 10,
    },
    {
        "name": "Credit Card Payment",
        "monthly_budget": 0,
        "type": "expense",
        "pre_deducted": False,
        "keywords": "credit card,cc payment,card payment,credit card bill,cc bill",
        "sort_order": 11,
    },
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(Category).count()
        if existing > 0:
            print(f"Categories already seeded ({existing} found). Skipping.")
            return

        for cat_data in CATEGORIES:
            cat = Category(**cat_data)
            db.add(cat)

        db.commit()
        print(f"Seeded {len(CATEGORIES)} categories.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
