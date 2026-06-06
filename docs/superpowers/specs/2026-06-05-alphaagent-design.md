# AlphaAgent — Design Spec

**Date:** 2026-06-05
**Status:** Approved

---

## Overview

AlphaAgent is a multi-agent stock research platform built as a portfolio project. When a user searches a ticker, 5 agents analyze it in parallel — 4 Python agents compute deterministic metrics (fundamentals, technical, sentiment, SEC filings), and a TypeScript Synthesis agent calls Gemini Flash to combine them into a narrative investment thesis. A scheduled daily pipeline pre-warms the cache for watchlist tickers each morning. A screener lets the user filter tickers by any scored metric, with email alerts when conditions are met.

**Primary goal:** Demonstrate Python-primary agent architecture, multi-agent orchestration via Trigger.dev, scheduled data pipelines via GitHub Actions, REST API design via FastAPI, and financial data API integration — all on a fully free stack.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend + API routes | Next.js (Vercel) |
| Python agents | FastAPI (Render free tier) |
| Agent orchestration | Trigger.dev (TypeScript tasks) |
| Database | PostgreSQL via Neon (free tier) |
| ORM | Prisma |
| Scheduled pipeline | GitHub Actions cron |
| Email alerts | Nodemailer (no third-party cost) |
| AI synthesis | Gemini Flash (free tier) |
| Stock data | yfinance (free, no API key) |
| News + sentiment | Finnhub free tier |
| SEC filings | EDGAR public API (data.sec.gov) |
| CI | GitHub Actions (lint, typecheck, test on push) |
| Version control | GitHub (public repo: `alphaagent`) |

---

## Architecture

```
User (browser)
     │
     ▼
Next.js on Vercel
  ├── /app pages (search, research, watchlist, screener, alerts)
  └── /api routes
        ├── POST /api/analyze/:ticker  → triggers Trigger.dev task
        ├── GET  /api/research/:ticker → reads from Neon
        ├── GET  /api/watchlist        → CRUD on watchlist table
        ├── GET  /api/screener         → filters research table by rules
        └── POST /api/alerts           → CRUD on alert_rules table
             │
             ▼
        Trigger.dev task: analyze_ticker
          ├── Parallel fan-out (4 subtasks)
          │     ├── GET http://fastapi.render.com/agents/fundamentals?ticker=X
          │     ├── GET http://fastapi.render.com/agents/technical?ticker=X
          │     ├── GET http://fastapi.render.com/agents/sentiment?ticker=X
          │     └── GET http://fastapi.render.com/agents/sec_filings?ticker=X
          │
          └── Synthesis subtask (after all 4 complete)
                ├── Computes weighted overall_score
                ├── Calls Gemini Flash → investment thesis
                └── Writes full result to Neon

Python FastAPI on Render (free tier)
  ├── GET /agents/fundamentals?ticker=  → yfinance metrics
  ├── GET /agents/technical?ticker=     → RSI, moving averages, volume
  ├── GET /agents/sentiment?ticker=     → Finnhub news sentiment
  └── GET /agents/sec_filings?ticker=   → EDGAR filings + insider data

GitHub Actions (cron: daily 6am ET)
  └── Calls POST /api/analyze/:ticker (Next.js → Trigger.dev) per watchlist ticker
  └── Waits for each to complete → results stored in Neon by Trigger.dev
  └── Checks alert_rules → sends email via Nodemailer if conditions met
```

**On-demand search flow:**
1. User searches "AAPL"
2. Next.js checks Neon for a `research` row with `status = 'complete'` and `analyzed_at` within 6 hours
3. If fresh → return immediately from Neon
4. If stale → insert a `status = 'pending'` row, trigger Trigger.dev task, return task ID
5. Frontend polls `GET /api/research/AAPL` every 2 seconds until `status = 'complete'`

**Scheduled flow:**
1. GitHub Actions runs at 6am ET daily
2. Calls `POST /api/analyze/:ticker` (Vercel) for each watchlist ticker — reuses the same Trigger.dev flow as on-demand
3. Trigger.dev tasks run the 4 FastAPI agents + synthesis, store results in Neon
4. After all tickers refresh, pipeline checks `alert_rules` and fires emails via Nodemailer where conditions are met

---

## Database Schema

```sql
-- Full analysis result per ticker per run
research (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker        text NOT NULL,
  analyzed_at   timestamptz NOT NULL DEFAULT now(),
  status        text NOT NULL,          -- 'pending' | 'complete' | 'error'
  overall_score float,                  -- weighted avg of 4 scores, 0–10
  thesis        text,                   -- Gemini Flash narrative
  recommendation text,                 -- 'bullish' | 'neutral' | 'bearish'
  fund_score    float,
  tech_score    float,
  sent_score    float,
  sec_score     float,
  fund_data     jsonb,
  tech_data     jsonb,
  sent_data     jsonb,
  sec_data      jsonb,
  error_msg     text
)

-- Tickers the daily GitHub Actions pipeline refreshes
watchlist (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker    text UNIQUE NOT NULL,
  added_at  timestamptz NOT NULL DEFAULT now()
)

-- Saved screener filter sets
screener_configs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  filters    jsonb NOT NULL,   -- [{field, operator, value}, ...]
  created_at timestamptz NOT NULL DEFAULT now()
)

-- Alert rules: email when screener conditions are met post-refresh
alert_rules (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name           text NOT NULL,
  filters        jsonb NOT NULL,
  email          text NOT NULL,
  is_active      boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  last_triggered timestamptz
)
```

**Notes:**
- `fund_data`, `tech_data`, `sent_data`, `sec_data` store raw metrics as `jsonb` — avoids 20+ columns while keeping data queryable via Postgres JSON operators
- Screener filters on scalar score columns (`fund_score`, `overall_score`, etc.) and on specific fields inside `jsonb` blobs (e.g. `rsi`, `pe_ratio`)
- No auth — personal tool, no login required

---

## Agent Design

All 4 Python agents are FastAPI route handlers. Each returns `{score: float, signals: string[], data: dict}`.

### Fundamentals Agent — `GET /agents/fundamentals?ticker=`
- **Source:** `yfinance`
- **Computes:** P/E ratio, revenue growth YoY, profit margin, debt-to-equity, EPS growth
- **Scoring:** High margin + revenue growth + low D/E → higher score. Negative earnings or D/E > 2 → low score.
- **Output fields:** `pe_ratio`, `revenue_growth_pct`, `profit_margin_pct`, `debt_to_equity`, `eps_growth_pct`

### Technical Agent — `GET /agents/technical?ticker=`
- **Source:** `yfinance` 1-year daily price history
- **Computes:** RSI (14-day), 50-day MA, 200-day MA, volume vs 20-day avg, price vs 52-week high
- **Scoring:** RSI 40–60 + price above 50MA + golden cross (50MA > 200MA) → higher score
- **Output fields:** `rsi`, `ma_50`, `ma_200`, `volume_ratio`, `price_vs_52w_high_pct`

### Sentiment Agent — `GET /agents/sentiment?ticker=`
- **Source:** Finnhub free tier (`/api/v1/news-sentiment`, `/api/v1/company-news`)
- **Computes:** Finnhub sentiment score + bullish/bearish article ratio over last 7 days
- **Scoring:** Derived directly from Finnhub's sentiment score, normalized to 0–10
- **Output fields:** `article_count`, `bullish_pct`, `bearish_pct`, `finnhub_score`, `top_headlines[]`

### SEC Filings Agent — `GET /agents/sec_filings?ticker=`
- **Source:** EDGAR public API (`data.sec.gov`) — no API key required
- **Computes:** Most recent 10-K and 10-Q dates, insider transaction net shares (30-day window), red flag phrases in filing text
- **Scoring:** Clean filings + net insider buying → higher score; red flags or heavy insider selling → lower
- **Red flag phrases:** "going concern", "material weakness", "guidance withdrawn", "restatement"
- **Output fields:** `last_10k_date`, `last_10q_date`, `insider_net_shares`, `red_flags[]`

### Synthesis Agent (TypeScript — Trigger.dev subtask)
- Waits for all 4 Python agents to complete
- Computes: `overall_score = (fund_score × 0.30) + (tech_score × 0.25) + (sent_score × 0.25) + (sec_score × 0.20)`
- Calls Gemini Flash with all 4 outputs in a structured prompt
- Gemini returns: 2–3 paragraph investment thesis + `recommendation` (`bullish` / `neutral` / `bearish`)
- Writes full result to `research` table in Neon

---

## API Routes (Next.js)

| Method | Route | Description |
|---|---|---|
| `POST` | `/api/analyze/:ticker` | Trigger Trigger.dev analyze task; returns `{id, status}` |
| `GET` | `/api/research/:ticker` | Latest research row for ticker; used for polling |
| `GET` | `/api/watchlist` | All watchlist tickers with latest research scores |
| `POST` | `/api/watchlist` | Add ticker to watchlist |
| `DELETE` | `/api/watchlist/:ticker` | Remove ticker from watchlist |
| `POST` | `/api/screener/run` | Run filters against research table; body: `{filters[]}` |
| `GET` | `/api/screener/configs` | List saved screener configs |
| `POST` | `/api/screener/configs` | Save a screener config |
| `GET` | `/api/alerts` | List alert rules |
| `POST` | `/api/alerts` | Create alert rule |
| `PATCH` | `/api/alerts/:id` | Toggle active/inactive |
| `DELETE` | `/api/alerts/:id` | Delete alert rule |

---

## Dashboard Pages

### `/` — Search
- Centered ticker search bar
- Live status indicator during analysis: "Fetching fundamentals… Running technical analysis…" (polls `/api/research/:ticker`)
- Watchlist grid below search: ticker cards with overall score badge and 1-day price change
- Recent searches shown as chips (last 5, stored in localStorage)

### `/research/[ticker]` — Research Report
- Header: ticker, company name, current price, overall score badge (color-coded: green ≥ 7, yellow 4–7, red < 4), `bullish / neutral / bearish` label
- Thesis card: Gemini's 2–3 paragraph investment thesis
- 2×2 grid of agent cards (Fundamentals, Technical, Sentiment, SEC Filings) — each shows score + key signals
- Expandable raw data section per agent
- "Add to Watchlist" button, `analyzed_at` timestamp

### `/watchlist` — Watchlist
- Table: ticker, company name, overall score, `fund_score`, `tech_score`, `sent_score`, `sec_score`, last analyzed, 1-day price change
- Click row → `/research/[ticker]`
- Add ticker input at top; remove button per row
- Scores pre-populated each morning by GitHub Actions pipeline

### `/screener` — Screener
- Filter builder: field dropdown + operator (`>`, `<`, `=`) + value input; add/remove filter rows
- Available fields: `overall_score`, `fund_score`, `tech_score`, `sent_score`, `sec_score`, `pe_ratio`, `rsi`, `debt_to_equity`, `revenue_growth_pct`
- "Run Screener" → queries Neon, shows matching tickers in a results table
- Save filter set with a name → stored in `screener_configs`
- Dropdown to load saved configs

### `/alerts` — Alerts
- Create alert: pick a saved screener config + enter email → saves to `alert_rules`
- List of active alert rules: name, filter summary, email, last triggered, active toggle
- GitHub Actions daily pipeline checks `alert_rules` after refreshing data, sends email via Nodemailer if conditions are met

---

## File Structure

```
alphaagent/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # lint, typecheck, test on push
│       └── daily_pipeline.yml      # 6am ET cron: refresh watchlist + check alerts
├── fastapi/
│   ├── main.py                     # FastAPI app entry point
│   ├── agents/
│   │   ├── fundamentals.py
│   │   ├── technical.py
│   │   ├── sentiment.py
│   │   └── sec_filings.py
│   ├── requirements.txt
│   └── Dockerfile
├── trigger/
│   └── analyze_ticker.ts           # Trigger.dev task: fan-out + synthesis
├── dashboard/                      # Next.js app
│   ├── app/
│   │   ├── page.tsx                # search
│   │   ├── research/[ticker]/
│   │   │   └── page.tsx
│   │   ├── watchlist/page.tsx
│   │   ├── screener/page.tsx
│   │   └── alerts/page.tsx
│   ├── app/api/                    # Next.js API routes
│   ├── lib/
│   │   ├── db.ts                   # Prisma client
│   │   └── gemini.ts               # Gemini Flash client
│   ├── components/
│   ├── prisma/
│   │   └── schema.prisma
│   └── package.json
├── scripts/
│   └── run_pipeline.py             # Called by GitHub Actions daily workflow
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## GitHub Actions Workflows

### `ci.yml` — Runs on every push
- Python: `pip install`, `pytest` on FastAPI agents
- TypeScript: `tsc --noEmit`, `eslint`, `jest` on Trigger.dev task and Next.js

### `daily_pipeline.yml` — Cron: `25 10 * * 1-5` (6:25am ET, weekdays)
1. Check out repo
2. Install Python deps, call `scripts/run_pipeline.py`
3. Pipeline calls FastAPI endpoints for each watchlist ticker
4. Stores results in Neon
5. Checks `alert_rules`, fires Nodemailer emails where conditions are met

---

## Out of Scope

- User authentication / multi-user support
- Real-time price streaming (WebSocket)
- Options data or derivatives analysis
- Mobile app
- Paid data sources
