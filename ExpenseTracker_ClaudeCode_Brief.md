# Expense Tracker + Analyser — Claude Code Build Brief

**For:** Dakshay Ahuja
**Goal:** A responsive expense tracker with an analytics dashboard and a Telegram bot front-end for frictionless logging, deployed as a free-tier web app. The end purpose is to surface category-level overspend and free up more room for SIPs/savings.

---

## 0. How to use this document

This entire file is meant to be **pasted into Claude Code as one block** — the Master Prompt in Section 1 tells Claude Code to read and follow the rest. Build in the phase order in Section 8: get the core tracker and dashboard working first, polish, then the Telegram bot, then deploy.

---

## 1. Master Prompt (this whole file is the prompt; Section 1 is the kickoff)

> Build me a personal expense tracker and analytics dashboard, plus a Telegram bot for logging expenses by text message, deployed as a free-tier web app. I'm a salaried software engineer in India; all amounts are in INR (Rs). Follow the full spec below in this file.
>
> **Stack:** Python + FastAPI backend exposed as serverless functions, **Neon or Supabase Postgres** for the database (free tier, persistent), a Telegram bot via **webhook** using `python-telegram-bot`, and a responsive single-page frontend (vanilla HTML/CSS/JS + Chart.js, no heavy framework). Frontend and API deploy to **Vercel** (or Netlify). See Section 7 for why SQLite/single-process does NOT work on serverless and what to do instead.
>
> **Core features:** (1) categorised expense + income logging, (2) a dashboard showing inflow/outflow summary and category breakdowns with budget-vs-actual, (3) a Telegram bot where I text "450 lunch" or "groceries 1200" and it auto-categorises and stores the expense.
>
> Build in phase order: Phase 1 (data model + API + manual web entry), Phase 2 (dashboard), Phase 3 (polish: dark mode, mobile, CSV import/export), Phase 4 (Telegram bot via webhook), Phase 5 (deploy to Vercel + Neon). Show me the running app after each phase before moving on. Use my budget config and category list exactly as specified. Read all secrets from environment variables, never hardcode tokens or DB URLs.

---

## 2. My financial context (bake this into the defaults)

Seed these as the monthly budget targets. The dashboard compares actual spend against them.

| Category | Monthly budget (Rs) | Notes |
|---|---|---|
| Housing | 26,500 | Rent Rs 21k + furniture installment Rs 5.5k |
| Transport | 24,000 | Fuel Rs 9k + car repayment to parents Rs 15k (flexible: Rs 10k-20k) |
| Food & Groceries | 15,000 | My share; partner splits separately |
| Subscriptions & Entertainment | 10,000 | |
| Utilities | 5,000 | |
| Miscellaneous | 5,000 | Clothes, dining out, gifts |
| Insurance | 1,500 | Extended company insurance policy. **Deducted at source**, see note below |
| **Total tracked expenses** | **87,000** | |
| Investments/SIP | 10,000 | Outflow but a *good* outflow, tag as `investment` |
| Emergency fund | 10,000 | AU Bank |
| Stocks/IPO buffer | 3,000 | Yes Bank |

**Normalised monthly take-home: Rs 1,07,396** — this is Rs 1,08,896 steady-state minus the Rs 1,500 insurance deducted at source. Use Rs 1,07,396 as the top-line inflow baseline.

**Insurance handling (important):** The Rs 1,500 insurance is its own expense category for visibility, but it is *deducted from salary at source*, so it never appears as a transaction I make. In the config, mark Insurance as `pre_deducted: true` and `type: structural`. The dashboard should:
- show it as already-spent (100% of budget, every month, automatically),
- exclude it from "lifestyle overspend" flags (I can't overspend a fixed deduction),
- not let it distort the savings-rate calculation (the money is gone before it lands, so income baseline is already net of it).

**Savings rate** = (income - lifestyle expenses) / income, where lifestyle = Food, Subs, Utilities, Misc, Housing, Transport (NOT investments, NOT the pre-deducted insurance). Investments count as *saved*, not spent.

**Key behavioural goal:** find Rs 3,000-5,000/month of optimisation, mostly in Food & Groceries (dining runs hot) and Miscellaneous. Make overspend in those categories impossible to miss.

---

## 3. Data model (Postgres)

**`transactions` table**
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| amount | NUMERIC(12,2) | Positive; sign derived from `type` |
| type | TEXT | `expense` \| `income` \| `investment` |
| category | TEXT | FK to category list |
| subcategory | TEXT | Optional ("dining out" under Food) |
| description | TEXT | Raw note |
| txn_date | DATE | Defaults to today |
| source | TEXT | `web` \| `telegram` |
| account | TEXT | Optional: HDFC / AU / Yes Bank |
| created_at | TIMESTAMPTZ | |

**`categories` table** — seed from Section 2. Columns: `name`, `monthly_budget`, `type` (`expense`/`investment`/`income`/`structural`), `pre_deducted` (bool), `keywords` (comma-separated for the Telegram auto-categoriser, e.g. Food -> "lunch,dinner,swiggy,zomato,groceries,blinkit,restaurant,cafe").

**`budgets` table** (optional) — `category`, `month`, `budget_amount`. If skipped in v1, read budgets off the categories table.

---

## 4. Backend API (FastAPI as serverless functions)

- `POST /api/transactions` — create (web form + Telegram)
- `GET /api/transactions?month=YYYY-MM&category=&type=` — list/filter
- `PUT /api/transactions/{id}` — edit miscategorised items
- `DELETE /api/transactions/{id}` — delete
- `GET /api/summary?month=YYYY-MM` — inflow, outflow, net, savings rate, per-category actual-vs-budget, top subcategories
- `GET /api/categories` / `POST /api/categories` — manage categories + budgets + keywords
- `GET /api/trends?months=6` — monthly totals per category
- `POST /api/telegram/webhook` — receives Telegram updates (Phase 4)

All money math server-side. Auto-inject the pre-deducted Insurance line into each month's summary so it always shows as spent.

---

## 5. Dashboard

Single responsive page, top-to-bottom:

1. **Month selector** + headline cards: Total Inflow, Total Outflow, Net Saved, Savings Rate (%). Savings-rate card green if >= 21.5%, amber below.
2. **Budget vs Actual** — horizontal bars per category, actual vs budget, bar turns red when over. Centrepiece; make overspend obvious. Insurance bar always full and visually muted (it's fixed).
3. **Outflow donut** — spend split by category.
4. **Good-vs-lifestyle split** — separate structural/investment outflow (SIP, emergency, stocks, car repayment, insurance) from lifestyle spend (food, subs, misc), so I see wealth-building vs consumption.
5. **Trend line** — 6-month category trends to catch dining/misc creep.
6. **Recent transactions** table — filterable, inline edit/delete, source badge (web/telegram).

**Design:** clean, modern, mobile-first, dark mode default. Chart.js for charts. Indian number formatting (Rs 1,07,396). No em-dashes in UI copy.

---

## 6. (reserved, see Section 8 for phase order and Section 9 for the bot spec)

---

## 7. Deployment architecture — READ THIS

I asked for a free-tier deploy on Vercel/Netlify. Those are **serverless**, important consequences:

- **SQLite will NOT work.** Serverless functions have ephemeral filesystems that reset between calls, so a SQLite file loses all data. Use a hosted Postgres with a free tier instead: **Neon** (recommended, generous free tier, serverless-friendly) or **Supabase**.
- **The Telegram bot must run as a WEBHOOK, not long-polling.** Long-polling needs an always-on process, which serverless doesn't give you. Register the bot's webhook to point at `POST /api/telegram/webhook` so Telegram pushes updates to the function. This is actually the cleaner fit for serverless.
- **Frontend + API** deploy together to Vercel (static frontend + Python serverless functions) or Netlify (with Netlify Functions).

**Secrets** (set as environment variables in the Vercel/Netlify dashboard, never in code):
```
DATABASE_URL=            # Neon/Supabase Postgres connection string
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET= # validate incoming webhook calls
```
Provide a `.env.example`. Never commit real secrets.

**Simpler fallback (if serverless gets fiddly):** keep the original single-process FastAPI + SQLite design and host on **Render / Railway / Fly.io** free tier, which give an always-on container with a persistent disk. The Telegram bot can then use long-polling. This is less "free-tier webapp" but far less rearchitecting. Claude Code: if the Vercel + Neon + webhook path hits repeated blockers, tell me and offer to switch to this.

---

## 8. Build phases (enforce this order)

| Phase | Deliverable | Done when |
|---|---|---|
| 1 | Postgres schema + FastAPI CRUD + minimal web form to add/list transactions | I can add an expense in the browser and see it listed |
| 2 | Full dashboard (summary cards, budget-vs-actual, donut, good-vs-lifestyle, trends, recent table) | Dashboard renders seeded budgets + the pre-deducted insurance line + live data |
| 3 | **Polish:** dark mode, mobile layout, CSV import/export, Indian number formatting, month rollover | Looks good on phone; I can export a month to CSV |
| 4 | **Telegram bot via webhook** (parse, store, auto-categorise, commands, whitelist) | I text the bot and the expense appears on the dashboard |
| 5 | **Deploy** to Vercel + Neon Postgres; register Telegram webhook; set env vars | Live URL works; bot works against the deployed API |

After each phase, run/deploy and show me before continuing.

---

## 9. Telegram bot spec (Phase 4)

**Flow:** I message the bot -> webhook fires -> parse -> store -> reply with the parsed category so I can correct it.

**Parsing rules:**
- Any order: "450 lunch", "lunch 450", "groceries 1200 blinkit".
- First number = amount. Remaining text = description.
- Auto-categorise by matching description words against each category's `keywords`. No match -> `Miscellaneous`, flagged in the reply.
- Default type `expense`. Leading `+` or "income"/"salary" -> `income`. "sip"/"invest" -> `investment`.
- Reply: `Rs 450 - Food & Groceries - "lunch" - saved. /fix to recategorise.`

**Commands:** `/start` (register/confirm my whitelisted chat ID), `/today`, `/month` (summaries from the same `/api/summary` logic), `/fix <id> <category>`, `/undo` (delete last).

**Security:** whitelist a single `TELEGRAM_ALLOWED_CHAT_ID`; ignore everyone else. Validate the webhook with `TELEGRAM_WEBHOOK_SECRET`. Token and IDs in env vars only.

**Setup notes Claude Code should print:** how to create the bot via @BotFather, how to find my chat ID, and the exact command to register the webhook URL after deploy.

---

## 10. Nice-to-haves (after Phase 5)

- CSV import to backfill from an HDFC statement export (mapped columns).
- A monthly "optimisation suggestion" panel: flag the 2 categories most over budget, show the rupee gap, framed as "redirect this to SIP".
- Recurring-transaction templates (rent, SIP, car repayment) auto-added on a set day.
- Single-password auth if exposed beyond me.

---

## 11. Constraints / preferences

- All currency Rs INR, Indian (lakh) number formatting.
- Free-tier hosting end to end (Vercel/Netlify + Neon/Supabase).
- Secrets only via env vars; `.env.example` provided; nothing real committed.
- No tracking, no third-party analytics.
- Clean, commented code; README covering local setup, deploy steps, bot creation, and webhook registration.
- No em-dashes in UI copy or generated text.
