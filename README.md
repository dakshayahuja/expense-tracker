# Personal Expense Tracker + Analyser

**Owner:** Dakshay Ahuja  
**Goal:** Track categorised expenses against monthly budgets, surface overspend, free up room for SIPs/savings. Telegram bot for frictionless logging. Deployed as a free-tier web app.

---

## Table of Contents

1. [Financial Context](#1-financial-context)
2. [Architecture](#2-architecture)
3. [Stack](#3-stack)
4. [Project Structure](#4-project-structure)
5. [Data Model](#5-data-model)
6. [API Reference](#6-api-reference)
7. [UI Design System](#7-ui-design-system)
8. [Test Suite](#8-test-suite)
9. [Phase Checklist](#9-phase-checklist)
10. [Local Development Setup](#10-local-development-setup)
11. [Deployment Guide](#11-deployment-guide)
12. [Telegram Bot Setup](#12-telegram-bot-setup)
13. [Environment Variables](#13-environment-variables)
14. [Known Issues / Pending Decisions](#14-known-issues--pending-decisions)

---

## 1. Financial Context

**Monthly take-home:** Rs 1,07,396 (Rs 1,08,896 steady-state minus Rs 1,500 insurance deducted at source)

### Budget targets

| Category | Monthly Budget (Rs) | Type | Notes |
|---|---|---|---|
| Housing | 26,500 | expense | Rent Rs 21k + furniture installment Rs 5.5k |
| Transport | 24,000 | expense | Fuel Rs 9k + car repayment to parents Rs 15k (flexible Rs 10k-20k) |
| Food & Groceries | 15,000 | expense | Personal share only; partner splits separately |
| Subscriptions & Entertainment | 10,000 | expense | |
| Utilities | 5,000 | expense | |
| Miscellaneous | 5,000 | expense | Clothes, dining out, gifts |
| Insurance | 1,500 | structural | **Pre-deducted at source** — never appears as a transaction |
| Investments/SIP | 10,000 | investment | Mutual funds via Groww/Zerodha |
| Emergency Fund | 10,000 | investment | AU Bank |
| Stocks/IPO | 3,000 | investment | Yes Bank account |
| **Total tracked** | **87,000** | | |

### Savings rate formula

```
Savings Rate = (Income - Lifestyle Spend) / Income

Lifestyle categories: Housing, Transport, Food & Groceries,
                      Subscriptions & Entertainment, Utilities, Miscellaneous

NOT included in lifestyle: Investments, Insurance (pre-deducted), Emergency Fund, Stocks
```

**Target savings rate:** >= 21.5% (dashboard shows green). Below 21.5% = amber. Below 10% = red.

### Insurance handling

- Pre-deducted from salary — never appears as a user transaction.
- Dashboard always shows Insurance as 100% spent (auto-injected in `/api/summary`).
- Excluded from lifestyle overspend flags and savings rate calculation.
- `pre_deducted: true` flag in the `categories` table.

### Key behaviour goal

Find Rs 3,000–5,000/month of optimisation. Hotspots: Food & Groceries (dining runs hot) and Miscellaneous. Overspend in those categories must be impossible to miss.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (SPA)                   │
│  Vanilla HTML/CSS/JS + Chart.js                     │
│  index.html (log expense) | dashboard.html          │
│  Deployed: Vercel static                            │
└────────────────────┬────────────────────────────────┘
                     │ fetch /api/*
┌────────────────────▼────────────────────────────────┐
│                FastAPI Backend                      │
│  api/index.py — single app, routers modular         │
│  Deployed: Vercel Python serverless functions       │
│  Each request is stateless (no shared memory)       │
└────────────────────┬────────────────────────────────┘
                     │ SQLAlchemy + psycopg2
┌────────────────────▼────────────────────────────────┐
│              Neon Postgres (free tier)              │
│  Persistent, serverless-friendly                    │
│  pool_pre_ping=True handles auto-suspend reconnects │
└─────────────────────────────────────────────────────┘

Telegram bot flow (Phase 5):
  User message → Telegram → POST /api/telegram/webhook
  → parse → store transaction → reply with category
  Webhook model required (no long-polling on serverless)
```

### Why not SQLite?

Vercel serverless functions have ephemeral filesystems — data written between requests is lost. Neon Postgres is persistent and has a serverless HTTP driver designed for this pattern.

### Why webhook for Telegram?

Long-polling needs an always-on process. Serverless gives you none. Telegram pushes updates to `/api/telegram/webhook` on each message — fits serverless perfectly.

---

## 3. Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | FastAPI (Python) | Fast, async-capable, automatic OpenAPI docs |
| ORM | SQLAlchemy 2.0 (sync) | Simple, works identically local and on Neon |
| Migrations | Alembic | Versioned schema changes, auto-generate from models |
| Database | Neon Postgres | Free tier, persistent, serverless-friendly |
| DB Driver | psycopg2-binary | Reliable sync driver; works with SQLAlchemy |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, deploys as static files |
| Charts | Chart.js 4.4 via CDN | Lightweight, good dark theme support |
| Deployment | Vercel | Free tier, handles static + Python serverless |
| Local DB | Docker Compose (postgres:16-alpine) | One command, isolated, no system install |
| Telegram | python-telegram-bot (Phase 4) | Webhook mode, well-documented |

---

## 4. Project Structure

```
expense-tracker/
├── api/
│   ├── __init__.py
│   ├── index.py          # FastAPI app entry point; mounts static frontend
│   ├── database.py       # SQLAlchemy engine + SessionLocal + get_db()
│   ├── models.py         # ORM models: Category, Transaction
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── seed.py           # Seeds 10 categories with budgets (run once)
│   ├── seed_demo.py      # Seeds 70 demo transactions across 6 months
│   └── routers/
│       ├── __init__.py
│       ├── categories.py  # GET/POST/PUT /api/categories
│       ├── transactions.py # GET/POST/PUT/DELETE /api/transactions
│       ├── summary.py     # GET /api/summary, GET /api/trends
│       ├── import_route.py # POST /api/import/parse (PDF bank statement parsing)
│       └── telegram.py    # POST /api/telegram/webhook (Phase 5)
│
├── frontend/
│   ├── index.html         # Log expense form + recent transactions
│   ├── dashboard.html     # Analytics dashboard (all charts)
│   ├── expenses.html      # Statement import + transaction management
│   ├── css/
│   │   ├── style.css      # Shared styles, single dark theme, Inter font
│   │   └── dashboard.css  # Dashboard headline cards, budget bars, charts
│   └── js/
│       ├── app.js         # Log expense + import logic (CSV + PDF bank statements)
│       └── dashboard.js   # Dashboard charts + data fetching
│
├── alembic/
│   ├── env.py             # Reads DATABASE_URL from .env
│   └── versions/
│       └── 2e4a29da9d20_initial_schema.py
│
├── docker-compose.yml     # Local Postgres (postgres:16-alpine, port 5432)
├── alembic.ini
├── requirements.txt
├── .env                   # Local secrets (gitignored)
├── .env.example           # Template — commit this, not .env
├── .gitignore
└── README.md              # This file
```

---

## 5. Data Model

### `categories` table

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| name | TEXT UNIQUE | e.g. "Food & Groceries" |
| monthly_budget | NUMERIC(12,2) | Budget per the brief |
| type | TEXT | `expense` / `investment` / `income` / `structural` |
| pre_deducted | BOOLEAN | True only for Insurance |
| keywords | TEXT | Comma-separated; used by Telegram auto-categoriser |
| sort_order | INTEGER | Display order in UI |

### `transactions` table

| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| amount | NUMERIC(12,2) | Always positive; sign derived from `type` |
| type | TEXT | `expense` / `income` / `investment` |
| category | TEXT | Must match a category name |
| subcategory | TEXT | Optional; e.g. "Dining out" under Food |
| description | TEXT | Raw note / merchant name |
| txn_date | DATE | Defaults to today |
| source | TEXT | `web` / `telegram` |
| account | TEXT | Optional: HDFC / AU Bank / Yes Bank / Cash |
| created_at | TIMESTAMPTZ | Auto-set by DB |

### Seeded categories (from `api/seed.py`)

```
Housing         — Rs 26,500 — keywords: rent, maintenance, furniture...
Transport       — Rs 24,000 — keywords: fuel, petrol, car, uber, ola...
Food & Groceries — Rs 15,000 — keywords: lunch, dinner, swiggy, zomato, blinkit...
Subscriptions & Entertainment — Rs 10,000 — keywords: netflix, spotify, prime...
Utilities       — Rs 5,000  — keywords: electricity, wifi, phone, gas...
Miscellaneous   — Rs 5,000  — keywords: clothes, gift, amazon, flipkart...
Insurance       — Rs 1,500  — pre_deducted=true, type=structural
Investments/SIP — Rs 10,000 — type=investment — keywords: sip, mutual fund...
Emergency Fund  — Rs 10,000 — type=investment — keywords: emergency, au bank...
Stocks/IPO      — Rs 3,000  — type=investment — keywords: stocks, ipo, yes bank...
```

---

## 6. API Reference

Base URL (local): `http://localhost:8000`

### Transactions

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/transactions` | List transactions. Params: `month=YYYY-MM`, `category=`, `type=` |
| `POST` | `/api/transactions` | Create transaction. Body: `TransactionCreate` schema |
| `PUT` | `/api/transactions/{id}` | Update fields. Body: `TransactionUpdate` (all fields optional) |
| `DELETE` | `/api/transactions/{id}` | Delete. Returns 204. |

### Categories

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/categories` | List all categories ordered by sort_order |
| `POST` | `/api/categories` | Create new category |
| `PUT` | `/api/categories/{id}` | Update category (budget, keywords, etc.) |

### Summary & Analytics

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/summary` | Monthly summary. Param: `month=YYYY-MM` (defaults to current month) |
| `GET` | `/api/trends` | Multi-month category totals. Param: `months=6` (1-24) |

### Summary response shape

```json
{
  "month": "2026-06",
  "total_income": 107396.0,
  "total_expense": 69150.0,
  "total_investment": 23000.0,
  "net_saved": 15246.0,
  "savings_rate": 35.6,
  "categories": [
    {
      "name": "Housing",
      "type": "expense",
      "pre_deducted": false,
      "budget": 26500.0,
      "actual": 26500.0,
      "remaining": 0.0,
      "pct_used": 100.0,
      "over_budget": false
    }
  ]
}
```

### PDF import

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/import/parse` | Parse bank PDF. Form fields: `bank` (au/yes/hdfc), `file`. Returns `{rows, count, bank}`. |

### Telegram webhook (Phase 5)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/telegram/webhook` | Receives Telegram updates. Validated via `TELEGRAM_WEBHOOK_SECRET` |

---

## 7. UI Design System

Single fixed matte dark theme (`--bg: #141417`). No theme switcher.

### Typography

- **Font:** Inter (Google Fonts) — loaded via `<link rel="preconnect">` in all HTML pages
- `font-feature-settings: "cv11", "ss01"` — enables optical letterforms and alternate digits
- `-webkit-font-smoothing: antialiased` / `font-smoothing: grayscale` — crisp rendering on Retina displays
- Amount values use `font-variant-numeric: tabular-nums` — columns stay aligned as digits change

### Headline cards (`dashboard.html`)

- 5 cards across on desktop (`grid-template-columns: repeat(5, 1fr)`)
- **Entry animation:** `hcard-in` keyframe (`opacity 0→1`, `translateY 10px→0`) with staggered `animation-delay` (0–240ms per card) — so cards appear in a left-to-right wave on load
- **Colour stripe:** each card gets a coloured top border via `inset 0 2px 0 <color>` box-shadow — layout-neutral vs `border-top`, so padding doesn't shift
  - Card 1 (Income) — emerald `rgba(16, 185, 129, 0.65)`
  - Card 2 (Expense) — rose `rgba(244, 63, 94, 0.65)`
  - Card 3 (Investments) — blue `rgba(96, 165, 250, 0.65)`
  - Card 4 (Net Saved) — neutral
  - Card 5 (Savings Rate) — dynamic: green/amber/red class driven by threshold
- **Value typography:** `1.75rem`, weight 800, `letter-spacing: -0.04em`; savings rate card bumped to `2.1rem`, `-0.05em`

### Savings rate card states

| Class | Threshold | Effect |
|---|---|---|
| `savings-green` | ≥ 21.5% | Emerald border + glow + green text |
| `savings-amber` | ≥ 10% | Amber border + amber text |
| `savings-red` | < 10% | Rose border + red text |

### Budget bars

- Track height: **10px** (was 8px) with `border-radius: 99px`
- Normal fill: `var(--bar-fill-color)` with `box-shadow: 0 0 10px var(--bar-fill-glow)` — glowing bar
- Over-budget: red gradient `#f43f5e → #e11d48` + `box-shadow: 0 0 8px var(--red-glow)`
- Pre-deducted (Insurance): `rgba(107,115,148,0.3)` muted fill, no glow
- Investment: blue gradient `#38bdf8 → #0ea5e9` + blue glow
- Hover row: subtle background highlight + negative horizontal padding expansion (8px)

### Import zone

- Dashed border (`1.5px dashed var(--border-hover)`) with background `var(--bg3)`
- Hover: border lightens + background shifts to `var(--bg4)` — looks like a real drop target

### Logo / section accents

- `.header h1::before` — 22×22 emerald rounded square logo mark
- `.card h2::before` — 3px vertical accent strip on section headers

### CSS variable naming

```
--bg, --bg2, --bg3, --bg4        — background layers
--border, --border-hover, --border-glow
--text, --text-muted, --text-dim
--accent, --accent-2, --accent-hover, --accent-glow
--green, --red, --blue, --amber  — semantic status colours
--green-glow, --red-glow, --blue-glow
--bar-fill-color, --bar-fill-glow
--ch1 to --ch10                  — chart palette
--chart-grid, --chart-tick, --chart-border
--chart-tooltip-bg/border/title/body
```

---

## 8. Test Suite

**149 tests, all passing.** Run: `pytest tests/ -q`

Tests use SQLite in-memory — no Postgres or Docker needed.

### `tests/conftest.py`

Shared pytest fixtures and app wiring.

| Fixture | Scope | Purpose |
|---|---|---|
| `_clear_db` (autouse) | function | Wipes all tables after every test — each test starts clean |
| `client` | function | `TestClient` wrapping the FastAPI app; overrides `get_db` to use SQLite |
| `db` | function | Raw `Session` for pre-seeding model objects in tests that need DB state |

**Key pattern:** `DATABASE_URL` is set to SQLite *before* any `api.*` import so `database.py` picks it up. Tests can run with `pytest tests/` — no env file needed.

### `tests/test_api.py` — Integration tests

Drives the real FastAPI routers over HTTP via `TestClient`. 100+ tests across 8 classes:

| Class | Tests | What it covers |
|---|---|---|
| `TestCategories` | 8 | CRUD, duplicate → 409, sort_order, keyword field, pre_deducted flag |
| `TestTransactionCRUD` | 20 | Create/read/update/delete, all type values, month/type/category filters, date-ordered list |
| `TestBulkImport` | 5 | `/api/transactions/bulk` — multi-row insert, empty list, validation, account field, month filter after import |
| `TestCSVExport` | 8 | Content-type, filename with/without month, header row format, data rows, month filter, date-ordered output |
| `TestSummary` | 15 | Income baseline constant (₹1,07,396 for any month), actual income override, expense/investment aggregation, net saved calc, insurance pre-deducted shows 100%, over-budget flag, savings rate formula, lifestyle-only categories |
| `TestTrends` | 6 | Default 6 months, `months` param, max 24, response shape, month key format, category totals |
| `TestImportParseEndpoint` | 8 | Missing `bank` field → 422, invalid bank → 400, non-PDF → 400, oversized file → 400, all 3 valid bank values accepted, real PDF integration tests (skipped if example file absent) |
| `TestSchemaValidation` | 5 | Pydantic validation: required fields (amount, txn_date, category), date format, category name+budget required |

### `tests/test_parsers.py` — Unit tests for PDF parsers

Pure Python — no HTTP, no database, no pdfplumber I/O. Uses stub classes (`_TablePage`, `_TextPage`) to inject fixture data.

| Class | Tests | What it covers |
|---|---|---|
| `TestParseAmount` | 9 | Indian lakh formatting (`2,82,805.00`), rupee symbol strip, empty/dash/non-numeric → 0.0 |
| `TestParseDateDmy` | 8 | `DD/MM/YY`, `DD/MM/YYYY`, dash separator, whitespace trim, invalid → None |
| `TestParseDateWords` | 9 | `26 May 2026`, 3-letter abbrevs, all 12 months, embedded in sentence, invalid month → None |
| `TestAutoCategory` | 8 | Case-insensitive keyword match, fallback to Miscellaneous, first-match wins |
| `TestShouldSkip` | 3 | Skips "total", "balance", "opening balance", empty string; does not skip real narrations |
| `TestCol` | 6 | Exact + substring + case-insensitive column header lookup, -1 for absent, multi-keyword fallback |
| `TestParseAuBank` | 8 | Debit→expense, credit→income, source=web, zero-row skip, total-row skip, multi-page accumulation, description truncated at 200 chars |
| `TestParseYesBank` | 5 | Withdrawal→expense, deposit→income, zero skip, balance-row skip, description truncation |
| `TestParseHdfcBank` | 8 | Balance-delta expense/income detection, sequential transactions, value-date stripped from narration, pure-digit ref stripped, no-amount line skipped |

---

## 9. Phase Checklist

### Phase 1 — Data model + API + web form

- [x] Docker Compose local Postgres setup
- [x] SQLAlchemy models: `Category`, `Transaction`
- [x] Alembic migrations (initial schema)
- [x] Seed script: 10 categories with exact budgets from brief
- [x] Demo seed: 70 transactions across 6 months
- [x] `GET /api/categories`
- [x] `POST /api/categories`
- [x] `PUT /api/categories/{id}`
- [x] `GET /api/transactions` with `month`, `category`, `type` filters
- [x] `POST /api/transactions`
- [x] `PUT /api/transactions/{id}`
- [x] `DELETE /api/transactions/{id}`
- [x] `GET /api/summary` with pre-deducted Insurance auto-injection
- [x] `GET /api/trends`
- [x] FastAPI serves frontend as static files
- [x] Log expense form (index.html)
- [x] Recent transactions table with inline Edit/Delete
- [x] Month + type filters on transaction list
- [x] `.env.example` with all required variables

### Phase 2 — Full dashboard

- [x] Month selector with prev/next navigation
- [x] 5 headline cards: Inflow, Outflow, Investments, Net Saved, Savings Rate
- [x] Savings rate colour: green >= 21.5%, amber >= 10%, red below
- [x] Budget vs Actual horizontal bars (all 10 categories)
- [x] Insurance bar shown as 100% auto, visually muted
- [x] Over-budget bars turn red with glow
- [x] Investment bars in blue
- [x] Outflow donut chart (spend breakdown by category)
- [x] Good-vs-lifestyle split doughnut
- [x] 6-month category trend line chart
- [x] Recent transactions table on dashboard with inline edit/delete
- [x] Charts rebuild when month changes
- [x] Baseline income fallback (Rs 1,07,396) when no income logged

### Phase 3 — Polish

- [x] Dark mode (default, always on — no light mode planned)
- [x] Mobile-first responsive layout
- [x] Indian number formatting (`Intl.NumberFormat('en-IN')`)
- [x] Single fixed matte dark theme (dark zinc, `--bg: #141417`) — no switcher
- [x] Glassmorphism sticky header with blur
- [x] Glowing budget bars, gradient headline cards
- [x] CSV export — download current month's transactions as `.csv`
- [x] CSV import — upload our own CSV export format, bulk insert
- [x] PDF bank statement import — AU Bank, Yes Bank, HDFC; bank selector dropdown; editable preview before confirm (`POST /api/import/parse`)
- [x] `GET /api/transactions/export` — CSV download with 8 columns
- [x] `POST /api/transactions/bulk` — bulk insert from import preview
- [x] Month rollover summary — auto-flag if previous month's budget exceeded
- [x] Optimisation suggestion panel — top 2 over-budget categories with rupee gap
- [x] Income baseline: ₹1,07,396 (₹1,08,896 gross − ₹1,500 insurance at source)

### Phase 4 — Deploy to Vercel + Neon

- [x] `vercel.json` configured (Python serverless + static CDN routing, 60MB Lambda limit)
- [x] CORS locked via `ALLOWED_ORIGIN` env var (wildcard for local dev, domain-restricted in prod)
- [x] `StaticFiles` mount disabled on Vercel (`VERCEL` env var check) — CDN serves frontend
- [x] `GET /api/health` endpoint added for uptime checks
- [ ] Neon account created, project + database set up
- [ ] Neon connection string added to Vercel env vars
- [ ] `ALLOWED_ORIGIN` set to production domain in Vercel env vars
- [ ] Vercel project created, linked to repo
- [ ] First deploy successful
- [ ] Alembic migrations run against Neon DB
- [ ] Seed categories on Neon DB
- [ ] GoDaddy domain pointed to Vercel (CNAME)
- [ ] Custom domain verified in Vercel dashboard
- [ ] End-to-end test: add expense via web → appears on dashboard

### Phase 5 — Telegram bot

- [ ] `python-telegram-bot` added to requirements.txt
- [ ] `api/routers/telegram.py` — POST `/api/telegram/webhook`
- [ ] Webhook secret validation (`TELEGRAM_WEBHOOK_SECRET` header check)
- [ ] Chat ID whitelist check (`TELEGRAM_ALLOWED_CHAT_ID`)
- [ ] Message parser: extracts amount + description from free text
  - Any order: "450 lunch" or "lunch 450" or "groceries 1200 blinkit"
  - First number = amount, rest = description
  - Leading `+` or "income"/"salary" keyword → type=income
  - "sip"/"invest" keyword → type=investment
  - Default type = expense
- [ ] Auto-categoriser: match description words against category keywords
  - No match → Miscellaneous, flagged in reply
- [ ] Bot reply format: `Rs 450 - Food & Groceries - "lunch" - saved. /fix to recategorise.`
- [ ] `/start` command — confirm whitelisted chat ID
- [ ] `/today` command — today's summary (total spent, per category)
- [ ] `/month` command — current month summary (calls same logic as /api/summary)
- [ ] `/fix <id> <category>` — recategorise last transaction
- [ ] `/undo` command — delete last transaction
- [ ] Webhook registration command printed in README
- [ ] Source badge shows "telegram" in transaction table
- [ ] Telegram webhook registered to production URL

### Extras (beyond phases, nice-to-have)

- [ ] Single-password auth (if app exposed beyond personal use)
- [ ] Recurring transaction templates (rent, SIP, car repayment auto-added on set day)
- [ ] CSV import from HDFC statement export (column mapping)
- [ ] Monthly email/Telegram summary at month end
- [ ] Budget edit UI (currently requires DB seed update)

---

## 9. Local Development Setup

### Prerequisites

- Docker Desktop (for local Postgres)
- Python 3.9+ with pyenv or system install
- Node.js not required (no build step)

### First-time setup

```bash
# 1. Clone and enter directory
cd expense-tracker

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env file
cp .env.example .env
# DATABASE_URL is pre-filled for local Docker Postgres — no changes needed

# 5. Start Postgres
docker compose up -d

# 6. Run migrations
alembic upgrade head

# 7. Seed categories
python -m api.seed

# 8. (Optional) Seed demo data for 6 months of transactions
python -m api.seed_demo

# 9. Start dev server
uvicorn api.index:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` (log expense) and `http://localhost:8000/dashboard.html`.

### Subsequent runs

```bash
source venv/bin/activate
docker compose up -d
uvicorn api.index:app --port 8000 --reload
```

### Running migrations after model changes

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

---

## 10. Deployment Guide

### Vercel + Neon

`vercel.json` is already committed. Python function (`api/index.py`) handles all `/api/*` requests. Frontend (`frontend/**`) served as static CDN assets.

#### Step 1: Neon database

1. Sign up at [neon.tech](https://neon.tech) — free, no credit card needed
2. Create project → name it `expense-tracker`
3. Copy the connection string (includes `?sslmode=require`):
   ```
   postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/expense_tracker?sslmode=require
   ```

#### Step 2: Run migrations on Neon

```bash
# One-time: run against Neon before first deploy
export DATABASE_URL="postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/expense_tracker?sslmode=require"
alembic upgrade head
python -m api.seed
```

#### Step 3: Vercel project

```bash
npm i -g vercel
vercel login
vercel          # follow prompts — link to GitHub repo or deploy from local
```

Add environment variables in Vercel dashboard (Settings → Environment Variables):

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string (with `?sslmode=require`) |
| `ALLOWED_ORIGIN` | Your production domain e.g. `https://expenses.yourdomain.com` |
| `TELEGRAM_BOT_TOKEN` | Set in Phase 5 |
| `TELEGRAM_ALLOWED_CHAT_ID` | Set in Phase 5 |
| `TELEGRAM_WEBHOOK_SECRET` | Set in Phase 5 |

> **CORS note:** `ALLOWED_ORIGIN` restricts the API to your domain only. Without it set, the API accepts requests from any origin — fine for local dev, a security gap on public URLs.

#### Step 4: Domain (GoDaddy)

In GoDaddy DNS:
```
Type:  CNAME
Name:  expenses  (or @ for root)
Value: cname.vercel-dns.com
TTL:   1 hour
```

Then in Vercel dashboard → Domains → Add `expenses.yourdomain.com`.

#### Step 5: Verify

```bash
# Health check
curl https://expenses.yourdomain.com/api/health
# Expected: {"status":"ok"}

# Verify frontend loads
open https://expenses.yourdomain.com
```

#### How the routing works

```
Request                         Handler
/api/summary?month=2026-06  →   api/index.py (Python serverless)
/api/import/parse           →   api/index.py (Python serverless)
/                           →   frontend/index.html (Vercel CDN)
/expenses.html              →   frontend/expenses.html (Vercel CDN)
/css/style.css              →   frontend/css/style.css (Vercel CDN)
/favicon.svg                →   frontend/favicon.svg (Vercel CDN)
```

`StaticFiles` in `api/index.py` is disabled on Vercel (detected via `VERCEL` env var) — static assets are served from CDN, not from the Python function.

---

## 11. Telegram Bot Setup

### Create the bot

1. Message `@BotFather` on Telegram
2. Send `/newbot`
3. Choose a name: e.g. `Dakshay Expense Bot`
4. Choose a username: e.g. `dakshay_expenses_bot`
5. Copy the token (looks like `123456789:ABCdef...`)
6. Set `TELEGRAM_BOT_TOKEN` in `.env` and Vercel env vars

### Find your chat ID

1. Message `@userinfobot` on Telegram
2. It replies with your user ID
3. Set `TELEGRAM_ALLOWED_CHAT_ID` to that number

### Register webhook (after deploy)

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-domain.com/api/telegram/webhook",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"
  }'
```

### Message format

```
450 lunch                     → Rs 450, Food & Groceries, "lunch"
groceries 1200 blinkit        → Rs 1200, Food & Groceries, "blinkit groceries"
+107396 salary                → Rs 1,07,396, income
sip 10000                     → Rs 10,000, investment, Investments/SIP
1800 dining out zomato        → Rs 1,800, Food & Groceries, "dining out zomato"
```

### Bot commands

| Command | Action |
|---|---|
| `/start` | Confirm chat ID is whitelisted |
| `/today` | Today's spend summary |
| `/month` | Current month summary |
| `/fix <id> <category>` | Recategorise a transaction |
| `/undo` | Delete last transaction |

---

## 12. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Postgres connection string. Local: `postgresql://expense_user:expense_pass@localhost:5432/expense_tracker` |
| `TELEGRAM_BOT_TOKEN` | Phase 4 | From @BotFather |
| `TELEGRAM_ALLOWED_CHAT_ID` | Phase 4 | Your Telegram user ID (integer) |
| `TELEGRAM_WEBHOOK_SECRET` | Phase 4 | Random secret for webhook validation (min 32 chars) |

See `.env.example` for template.

---

## 13. Known Issues / Pending Decisions

| # | Issue | Status | Notes |
|---|---|---|---|
| 1 | Income transaction in seed_demo uses `category="Housing"` | Low priority | Doesn't affect calculations (income type excluded from category_actuals). Fix if importing real data. |
| 2 | No auth | Deferred to Phase 5+ | App currently open on localhost. Fine for local use. Add single-password auth before public deploy. |
| 3 | Budget amounts hardcoded in seed | Accepted | `api/seed.py` is source of truth for budgets. To change, update seed + re-seed or update via `PUT /api/categories/{id}`. |
| 4 | No auth on API endpoints | Accepted for personal use | `ALLOWED_ORIGIN` restricts browser-based CORS. Direct curl is still open. Add single-password auth (Phase 5+ extras) if app is shared. |
| 5 | Neon free tier connection limit | Monitor | 10 concurrent connections on free tier. `pool_pre_ping=True` handles stale connections. Add `pool_size=1` if hitting limits. |
| 6 | Chart.js loaded from CDN | Acceptable | Pin version `4.4.4`. Consider vendoring if offline use needed. |
| 7 | Transport category: car repayment flexibility | Accepted | Brief says Rs 10k-20k flexible. Budgeted at Rs 24k (Rs 9k fuel + Rs 15k max). No special handling needed. |
| 8 | No pagination on transaction list | Deferred | Fine for personal use (few hundred rows/month). Add `limit`/`offset` to `/api/transactions` if needed. |

---

## Session Log

Track what was built in each Claude Code session.

| Date | Session Summary |
|---|---|
| 2026-06-28 | Phase 1 complete: Docker Postgres, SQLAlchemy models, Alembic migrations, full CRUD API, log expense web form, seed data |
| 2026-06-28 | Phase 2 complete: Full dashboard — headline cards, budget bars, donut chart, split chart, 6-month trend line, transactions table |
| 2026-06-29 | Phase 3 complete: Single dark theme, Inter font + optical letterforms, staggered card animations, coloured top stripes via inset box-shadow, 10px glowing budget bars, dashed import zone, section accent strips. CSV export/import, PDF bank statement import (AU Bank / Yes Bank / HDFC), bulk insert, rollover banner, optimisation suggestions, income baseline ₹1,07,396 constant. 149 tests passing. |
| 2026-06-29 | Test fixes: removed stale date-aware income baseline tests (test_income_baseline_july_2026, test_income_baseline_post_july) — replaced with test_income_baseline_constant_any_month. README rewritten with UI design system + test suite documentation. Phases reordered: Phase 4 = Vercel deploy, Phase 5 = Telegram. |
