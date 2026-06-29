"""
Integration tests for all FastAPI endpoints.
Uses SQLite via conftest.py; no Postgres required.
"""
import io
import pytest
from decimal import Decimal


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _txn(client, **kwargs):
    """Create a transaction and return the response JSON."""
    defaults = {
        "amount": 500.0,
        "type": "expense",
        "category": "Food & Groceries",
        "txn_date": "2026-05-15",
        "source": "web",
    }
    defaults.update(kwargs)
    return client.post("/api/transactions", json=defaults).json()


def _cat(client, name="Food & Groceries", budget=15000, **kwargs):
    return client.post("/api/categories", json={
        "name": name,
        "monthly_budget": budget,
        "type": "expense",
        **kwargs,
    }).json()


# ─── Categories ───────────────────────────────────────────────────────────────

class TestCategories:
    def test_list_empty(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_category(self, client):
        resp = client.post("/api/categories", json={
            "name": "Housing", "monthly_budget": 26500, "type": "expense", "sort_order": 1
        })
        assert resp.status_code == 201
        d = resp.json()
        assert d["name"] == "Housing"
        assert float(d["monthly_budget"]) == 26500.0
        assert d["type"] == "expense"
        assert "id" in d

    def test_list_ordered_by_sort_order(self, client):
        client.post("/api/categories", json={"name": "Z-cat", "monthly_budget": 100, "type": "expense", "sort_order": 99})
        client.post("/api/categories", json={"name": "A-cat", "monthly_budget": 100, "type": "expense", "sort_order": 1})
        cats = client.get("/api/categories").json()
        assert cats[0]["name"] == "A-cat"
        assert cats[1]["name"] == "Z-cat"

    def test_create_duplicate_returns_409(self, client):
        payload = {"name": "Housing", "monthly_budget": 26500, "type": "expense"}
        client.post("/api/categories", json=payload)
        resp = client.post("/api/categories", json=payload)
        assert resp.status_code == 409

    def test_update_category(self, client):
        cat_id = _cat(client)["id"]
        resp = client.put(f"/api/categories/{cat_id}", json={
            "name": "Food & Groceries",
            "monthly_budget": 18000,
            "type": "expense",
        })
        assert resp.status_code == 200
        assert float(resp.json()["monthly_budget"]) == 18000.0

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put("/api/categories/9999", json={
            "name": "X", "monthly_budget": 100, "type": "expense"
        })
        assert resp.status_code == 404

    def test_category_keywords_stored(self, client):
        resp = client.post("/api/categories", json={
            "name": "Transport",
            "monthly_budget": 24000,
            "type": "expense",
            "keywords": "uber,ola,fuel",
        })
        assert resp.json()["keywords"] == "uber,ola,fuel"

    def test_pre_deducted_flag_stored(self, client):
        resp = client.post("/api/categories", json={
            "name": "Insurance",
            "monthly_budget": 1500,
            "type": "structural",
            "pre_deducted": True,
        })
        assert resp.json()["pre_deducted"] is True


# ─── Transactions CRUD ────────────────────────────────────────────────────────

class TestTransactionCRUD:
    def test_list_empty(self, client):
        assert client.get("/api/transactions").json() == []

    def test_create_returns_201(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 749.0, "type": "expense",
            "category": "Food & Groceries", "txn_date": "2026-05-26",
        })
        assert resp.status_code == 201

    def test_create_persists_all_fields(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 749.0, "type": "expense",
            "category": "Subscriptions & Entertainment",
            "subcategory": "streaming",
            "description": "Apple TV+",
            "txn_date": "2026-05-26",
            "source": "web",
            "account": "AU Bank",
        })
        d = resp.json()
        assert float(d["amount"]) == 749.0
        assert d["type"] == "expense"
        assert d["subcategory"] == "streaming"
        assert d["description"] == "Apple TV+"
        assert d["account"] == "AU Bank"
        assert "id" in d
        assert "created_at" in d

    def test_create_validates_negative_amount(self, client):
        resp = client.post("/api/transactions", json={
            "amount": -100.0, "type": "expense",
            "category": "Food & Groceries", "txn_date": "2026-05-15",
        })
        assert resp.status_code == 422

    def test_create_validates_zero_amount(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 0, "type": "expense",
            "category": "Food & Groceries", "txn_date": "2026-05-15",
        })
        assert resp.status_code == 422

    def test_create_validates_invalid_type(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 100, "type": "transfer",
            "category": "Misc", "txn_date": "2026-05-15",
        })
        assert resp.status_code == 422

    def test_create_all_valid_types(self, client):
        for txn_type in ("expense", "income", "investment"):
            resp = client.post("/api/transactions", json={
                "amount": 100, "type": txn_type,
                "category": "Misc", "txn_date": "2026-05-15",
            })
            assert resp.status_code == 201, f"type={txn_type} failed"

    def test_list_returns_created(self, client):
        _txn(client, amount=100)
        _txn(client, amount=200)
        txns = client.get("/api/transactions").json()
        assert len(txns) == 2

    def test_list_ordered_by_date_desc(self, client):
        _txn(client, txn_date="2026-05-01")
        _txn(client, txn_date="2026-05-20")
        txns = client.get("/api/transactions").json()
        assert txns[0]["txn_date"] == "2026-05-20"
        assert txns[1]["txn_date"] == "2026-05-01"

    def test_filter_by_month(self, client):
        _txn(client, txn_date="2026-05-10", amount=100)
        _txn(client, txn_date="2026-06-10", amount=200)
        resp = client.get("/api/transactions?month=2026-05")
        assert len(resp.json()) == 1
        assert float(resp.json()[0]["amount"]) == 100.0

    def test_filter_by_month_excludes_adjacent(self, client):
        _txn(client, txn_date="2026-04-30")  # day before May
        _txn(client, txn_date="2026-05-01")  # first of May
        _txn(client, txn_date="2026-05-31")  # last of May
        _txn(client, txn_date="2026-06-01")  # first of June
        resp = client.get("/api/transactions?month=2026-05")
        assert len(resp.json()) == 2

    def test_filter_by_type_expense(self, client):
        _txn(client, type="expense")
        _txn(client, type="income", amount=107396)
        _txn(client, type="investment", amount=10000)
        resp = client.get("/api/transactions?type=expense")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["type"] == "expense"

    def test_filter_by_type_income(self, client):
        _txn(client, type="income", amount=107396)
        _txn(client, type="expense")
        resp = client.get("/api/transactions?type=income")
        assert all(t["type"] == "income" for t in resp.json())

    def test_filter_by_category(self, client):
        _txn(client, category="Food & Groceries")
        _txn(client, category="Transport", amount=1000)
        resp = client.get("/api/transactions?category=Transport")
        assert len(resp.json()) == 1
        assert resp.json()[0]["category"] == "Transport"

    def test_invalid_month_format_returns_400(self, client):
        resp = client.get("/api/transactions?month=2026/05")
        assert resp.status_code == 400

    def test_update_amount(self, client):
        txn_id = _txn(client, amount=100)["id"]
        resp = client.put(f"/api/transactions/{txn_id}", json={"amount": 250.0})
        assert resp.status_code == 200
        assert float(resp.json()["amount"]) == 250.0

    def test_update_category(self, client):
        txn_id = _txn(client)["id"]
        resp = client.put(f"/api/transactions/{txn_id}", json={"category": "Transport"})
        assert resp.json()["category"] == "Transport"

    def test_update_partial_fields_only(self, client):
        txn_id = _txn(client, amount=100, description="original")["id"]
        client.put(f"/api/transactions/{txn_id}", json={"amount": 999.0})
        updated = client.get(f"/api/transactions?month=2026-05").json()
        assert float(updated[0]["amount"]) == 999.0
        assert updated[0]["description"] == "original"  # unchanged

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put("/api/transactions/9999", json={"amount": 100})
        assert resp.status_code == 404

    def test_delete_transaction(self, client):
        txn_id = _txn(client)["id"]
        resp = client.delete(f"/api/transactions/{txn_id}")
        assert resp.status_code == 204
        assert client.get("/api/transactions").json() == []

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/transactions/9999")
        assert resp.status_code == 404

    def test_delete_does_not_affect_other_transactions(self, client):
        id1 = _txn(client, amount=100)["id"]
        id2 = _txn(client, amount=200)["id"]
        client.delete(f"/api/transactions/{id1}")
        remaining = client.get("/api/transactions").json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == id2


# ─── Bulk Import ──────────────────────────────────────────────────────────────

class TestBulkImport:
    def test_import_multiple_rows(self, client):
        payload = [
            {"amount": 500, "type": "expense", "category": "Food & Groceries",
             "txn_date": "2026-05-15", "source": "web", "description": "lunch"},
            {"amount": 300, "type": "expense", "category": "Transport",
             "txn_date": "2026-05-16", "source": "web", "description": "uber"},
        ]
        resp = client.post("/api/transactions/bulk", json=payload)
        assert resp.status_code == 201
        assert resp.json()["imported"] == 2
        assert len(client.get("/api/transactions").json()) == 2

    def test_import_empty_list(self, client):
        resp = client.post("/api/transactions/bulk", json=[])
        assert resp.status_code == 201
        assert resp.json()["imported"] == 0

    def test_import_validates_negative_amount(self, client):
        payload = [{"amount": -100, "type": "expense",
                    "category": "Food & Groceries", "txn_date": "2026-05-15"}]
        resp = client.post("/api/transactions/bulk", json=payload)
        assert resp.status_code == 422

    def test_import_preserves_account_field(self, client):
        payload = [{
            "amount": 749, "type": "expense", "category": "Subscriptions & Entertainment",
            "txn_date": "2026-05-26", "source": "web", "account": "AU Bank",
        }]
        client.post("/api/transactions/bulk", json=payload)
        txns = client.get("/api/transactions").json()
        assert txns[0]["account"] == "AU Bank"

    def test_import_then_list_by_month(self, client):
        payload = [
            {"amount": 100, "type": "expense", "category": "Misc",
             "txn_date": "2026-05-10", "source": "web"},
            {"amount": 200, "type": "expense", "category": "Misc",
             "txn_date": "2026-06-10", "source": "web"},
        ]
        client.post("/api/transactions/bulk", json=payload)
        resp = client.get("/api/transactions?month=2026-05")
        assert len(resp.json()) == 1


# ─── CSV Export ───────────────────────────────────────────────────────────────

class TestCSVExport:
    def test_returns_csv_content_type(self, client):
        _txn(client)
        resp = client.get("/api/transactions/export?month=2026-05")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_attachment_filename_with_month(self, client):
        resp = client.get("/api/transactions/export?month=2026-05")
        assert 'filename="expenses_2026-05.csv"' in resp.headers["content-disposition"]

    def test_attachment_filename_without_month(self, client):
        resp = client.get("/api/transactions/export")
        assert 'filename="expenses_all.csv"' in resp.headers["content-disposition"]

    def test_header_row_correct(self, client):
        resp = client.get("/api/transactions/export?month=2026-05")
        lines = resp.text.strip().split("\n")
        assert lines[0] == "Date,Description,Subcategory,Category,Type,Amount,Account,Source"

    def test_data_row_contains_expected_fields(self, client):
        _txn(client, amount=749, description="Apple TV+",
             category="Subscriptions & Entertainment", account="AU Bank")
        lines = client.get("/api/transactions/export?month=2026-05").text.strip().split("\n")
        assert len(lines) == 2  # header + 1 row
        assert "Apple TV+" in lines[1]
        assert "749" in lines[1]
        assert "AU Bank" in lines[1]

    def test_month_filter_applied_to_export(self, client):
        _txn(client, txn_date="2026-05-10", amount=100)
        _txn(client, txn_date="2026-06-10", amount=200)
        lines = client.get("/api/transactions/export?month=2026-05").text.strip().split("\n")
        assert len(lines) == 2  # header + 1

    def test_export_all_without_month(self, client):
        for i in range(1, 4):
            _txn(client, txn_date=f"2026-0{i}-01", amount=100 * i)
        lines = client.get("/api/transactions/export").text.strip().split("\n")
        assert len(lines) == 4  # header + 3

    def test_invalid_month_format_returns_400(self, client):
        resp = client.get("/api/transactions/export?month=2026/05")
        assert resp.status_code == 400

    def test_export_ordered_by_date_asc(self, client):
        _txn(client, txn_date="2026-05-20", description="late")
        _txn(client, txn_date="2026-05-01", description="early")
        lines = client.get("/api/transactions/export?month=2026-05").text.strip().split("\n")
        assert "early" in lines[1]
        assert "late" in lines[2]


# ─── Summary ──────────────────────────────────────────────────────────────────

class TestSummary:
    def test_returns_correct_month(self, client):
        resp = client.get("/api/summary?month=2026-05")
        assert resp.json()["month"] == "2026-05"

    def test_income_baseline_constant_any_month(self, client):
        # ₹1,07,396 = ₹1,08,896 gross − ₹1,500 insurance at source. Constant, never date-aware.
        for month in ("2026-06", "2026-07", "2027-01"):
            resp = client.get(f"/api/summary?month={month}")
            assert float(resp.json()["total_income"]) == pytest.approx(107_396.0), \
                f"month={month} got wrong baseline"

    def test_actual_income_overrides_baseline(self, client):
        _txn(client, amount=120_000, type="income",
             category="Income", txn_date="2026-05-01")
        resp = client.get("/api/summary?month=2026-05")
        assert float(resp.json()["total_income"]) == pytest.approx(120_000.0)

    def test_total_expense_aggregated(self, client):
        _txn(client, amount=5000, type="expense", txn_date="2026-05-10")
        _txn(client, amount=3000, type="expense", txn_date="2026-05-20")
        data = client.get("/api/summary?month=2026-05").json()
        assert float(data["total_expense"]) == pytest.approx(8000.0)

    def test_total_investment_aggregated(self, client):
        _txn(client, amount=10_000, type="investment",
             category="Investments/SIP", txn_date="2026-05-05")
        data = client.get("/api/summary?month=2026-05").json()
        assert float(data["total_investment"]) == pytest.approx(10_000.0)

    def test_net_saved_calculation(self, client):
        _txn(client, amount=50_000, type="income", txn_date="2026-05-01")
        _txn(client, amount=10_000, type="expense", txn_date="2026-05-10")
        _txn(client, amount=5_000, type="investment", txn_date="2026-05-15")
        data = client.get("/api/summary?month=2026-05").json()
        assert float(data["net_saved"]) == pytest.approx(35_000.0)

    def test_insurance_pre_deducted_shows_full_budget(self, client, db):
        from api.models import Category
        db.add(Category(
            name="Insurance", monthly_budget=1500,
            type="structural", pre_deducted=True, sort_order=7,
        ))
        db.commit()
        data = client.get("/api/summary?month=2026-05").json()
        ins = next(c for c in data["categories"] if c["name"] == "Insurance")
        # Always shows as 100% spent regardless of recorded transactions
        assert ins["pct_used"] == pytest.approx(100.0)
        assert float(ins["actual"]) == pytest.approx(1500.0)

    def test_over_budget_flag_true_when_exceeded(self, client, db):
        from api.models import Category
        db.add(Category(name="Food & Groceries", monthly_budget=15_000,
                        type="expense", sort_order=3))
        db.commit()
        _txn(client, amount=20_000, category="Food & Groceries", txn_date="2026-05-10")
        data = client.get("/api/summary?month=2026-05").json()
        food = next(c for c in data["categories"] if c["name"] == "Food & Groceries")
        assert food["over_budget"] is True

    def test_over_budget_flag_false_within_budget(self, client, db):
        from api.models import Category
        db.add(Category(name="Food & Groceries", monthly_budget=15_000,
                        type="expense", sort_order=3))
        db.commit()
        _txn(client, amount=5_000, category="Food & Groceries", txn_date="2026-05-10")
        data = client.get("/api/summary?month=2026-05").json()
        food = next(c for c in data["categories"] if c["name"] == "Food & Groceries")
        assert food["over_budget"] is False

    def test_savings_rate_with_no_lifestyle_spend(self, client):
        # 100% income, 0 lifestyle spend → savings rate 100%
        data = client.get("/api/summary?month=2026-05").json()
        assert data["savings_rate"] == pytest.approx(100.0)

    def test_savings_rate_below_100_with_lifestyle_spend(self, client):
        _txn(client, amount=107_396, type="income", txn_date="2026-05-01")
        _txn(client, amount=30_000, type="expense",
             category="Housing", txn_date="2026-05-05")
        data = client.get("/api/summary?month=2026-05").json()
        expected = round((107_396 - 30_000) / 107_396 * 100, 1)
        assert data["savings_rate"] == pytest.approx(expected, abs=0.2)

    def test_only_lifestyle_categories_affect_savings_rate(self, client):
        # Investment spend should NOT reduce savings rate
        _txn(client, amount=107_396, type="income", txn_date="2026-05-01")
        _txn(client, amount=10_000, type="investment",
             category="Investments/SIP", txn_date="2026-05-05")
        data = client.get("/api/summary?month=2026-05").json()
        # Savings rate should still be 100% (investments excluded from lifestyle)
        assert data["savings_rate"] == pytest.approx(100.0)

    def test_no_month_param_defaults_to_current_month(self, client):
        from datetime import date
        today = date.today()
        resp = client.get("/api/summary")
        assert resp.json()["month"] == f"{today.year}-{today.month:02d}"

    def test_categories_list_in_response(self, client, db):
        from api.models import Category
        db.add(Category(name="Housing", monthly_budget=26_500,
                        type="expense", sort_order=1))
        db.commit()
        data = client.get("/api/summary?month=2026-05").json()
        assert any(c["name"] == "Housing" for c in data["categories"])


# ─── Trends ───────────────────────────────────────────────────────────────────

class TestTrends:
    def test_default_six_months(self, client):
        resp = client.get("/api/trends")
        assert resp.status_code == 200
        assert len(resp.json()) == 6

    def test_custom_months_param(self, client):
        resp = client.get("/api/trends?months=3")
        assert len(resp.json()) == 3

    def test_max_24_months(self, client):
        resp = client.get("/api/trends?months=24")
        assert len(resp.json()) == 24

    def test_each_entry_has_month_and_categories(self, client):
        data = client.get("/api/trends?months=2").json()
        for entry in data:
            assert "month" in entry
            assert "categories" in entry
            assert isinstance(entry["categories"], dict)

    def test_month_key_format(self, client):
        data = client.get("/api/trends?months=1").json()
        import re
        assert re.match(r"\d{4}-\d{2}", data[0]["month"])

    def test_category_totals_aggregated_correctly(self, client):
        _txn(client, amount=1000, category="Transport", txn_date="2026-05-10")
        _txn(client, amount=500, category="Transport", txn_date="2026-05-20")
        data = client.get("/api/trends?months=2").json()
        may_entry = next((e for e in data if e["month"] == "2026-05"), None)
        if may_entry:
            assert may_entry["categories"].get("Transport") == pytest.approx(1500.0)


# ─── PDF Import Endpoint ───────────────────────────────────────────────────────

class TestImportParseEndpoint:
    def test_missing_bank_field_returns_422(self, client):
        resp = client.post(
            "/api/import/parse",
            files={"file": ("stmt.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert resp.status_code == 422

    def test_invalid_bank_value_returns_400(self, client):
        resp = client.post(
            "/api/import/parse",
            files={"file": ("stmt.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            data={"bank": "chase"},
        )
        assert resp.status_code == 400
        assert "bank must be one of" in resp.json()["detail"]

    def test_non_pdf_file_returns_400(self, client):
        resp = client.post(
            "/api/import/parse",
            files={"file": ("stmt.csv", io.BytesIO(b"Date,Amount"), "text/csv")},
            data={"bank": "hdfc"},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    def test_oversized_file_returns_400(self, client):
        big = io.BytesIO(b"X" * (11 * 1024 * 1024))
        resp = client.post(
            "/api/import/parse",
            files={"file": ("big.pdf", big, "application/pdf")},
            data={"bank": "hdfc"},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"]

    def test_all_valid_bank_values_accepted_syntax_wise(self, client):
        for bank in ("au", "yes", "hdfc"):
            # minimal PDF body that will fail inside pdfplumber but pass validation
            resp = client.post(
                "/api/import/parse",
                files={"file": ("s.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                data={"bank": bank},
            )
            # 400 from pdfplumber (can't parse fake PDF), NOT 422 (schema) or 400 (invalid bank)
            assert resp.status_code in (400,), f"bank={bank} got {resp.status_code}"
            if resp.status_code == 400:
                assert "bank must be one of" not in resp.json()["detail"]

    def test_real_au_bank_pdf(self, client):
        import os
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "example-statements", "Account Statement_xx7976.pdf"
        )
        if not os.path.exists(pdf_path):
            pytest.skip("AU Bank example PDF not present")
        with open(pdf_path, "rb") as f:
            resp = client.post(
                "/api/import/parse",
                files={"file": ("au.pdf", f, "application/pdf")},
                data={"bank": "au"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank"] == "au"
        assert data["count"] > 0
        for row in data["rows"]:
            assert row["type"] in ("expense", "income", "investment")
            assert float(row["amount"]) > 0
            assert row["account"] == "AU Bank"

    def test_real_yes_bank_pdf(self, client):
        import os
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "example-statements",
            "Account_Statement_25_May_2026-20_Jun_2026.pdf"
        )
        if not os.path.exists(pdf_path):
            pytest.skip("Yes Bank example PDF not present")
        with open(pdf_path, "rb") as f:
            resp = client.post(
                "/api/import/parse",
                files={"file": ("yes.pdf", f, "application/pdf")},
                data={"bank": "yes"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank"] == "yes"
        assert data["count"] > 0

    def test_real_hdfc_pdf(self, client):
        import os
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "example-statements",
            "Acct_Statement_XXXXXXXX5393_20062026May.pdf"
        )
        if not os.path.exists(pdf_path):
            pytest.skip("HDFC example PDF not present")
        with open(pdf_path, "rb") as f:
            resp = client.post(
                "/api/import/parse",
                files={"file": ("hdfc.pdf", f, "application/pdf")},
                data={"bank": "hdfc"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank"] == "hdfc"
        assert data["count"] > 0


# ─── Schemas (Pydantic validation) ────────────────────────────────────────────

class TestSchemaValidation:
    def test_transaction_requires_amount(self, client):
        resp = client.post("/api/transactions", json={
            "type": "expense", "category": "Misc", "txn_date": "2026-05-01"
        })
        assert resp.status_code == 422

    def test_transaction_requires_txn_date(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 100, "type": "expense", "category": "Misc"
        })
        assert resp.status_code == 422

    def test_transaction_requires_category(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 100, "type": "expense", "txn_date": "2026-05-01"
        })
        assert resp.status_code == 422

    def test_transaction_date_format_validated(self, client):
        resp = client.post("/api/transactions", json={
            "amount": 100, "type": "expense",
            "category": "Misc", "txn_date": "not-a-date"
        })
        assert resp.status_code == 422

    def test_category_requires_name_and_budget(self, client):
        resp = client.post("/api/categories", json={"type": "expense"})
        assert resp.status_code == 422
