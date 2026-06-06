# AlphaAgent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-agent stock research platform with 4 parallel Python agents (FastAPI on Render), a Trigger.dev TypeScript synthesis task, a Next.js dashboard (Vercel), and a GitHub Actions daily pipeline — all free.

**Architecture:** Python FastAPI service hosts 4 agent endpoints (fundamentals, technical, sentiment, SEC filings). A Trigger.dev TypeScript task fans out to all 4 in parallel, then calls Gemini Flash for synthesis and writes to Neon. Next.js API routes trigger the task and serve the dashboard. GitHub Actions refreshes watchlist tickers daily and fires Nodemailer email alerts.

**Tech Stack:** Python 3.11+, FastAPI, yfinance, httpx, pytest — TypeScript, Next.js 14 (App Router), Prisma, Trigger.dev v3, @google/generative-ai, Nodemailer — PostgreSQL (Neon), Vercel, Render free tier, GitHub Actions

---

## File Structure

```
alphaagent/
├── .github/
│   └── workflows/
│       ├── ci.yml                        # lint + test on every push
│       └── daily_pipeline.yml            # 6:25am ET cron, weekdays
├── fastapi/
│   ├── main.py                           # FastAPI app, mounts all routers
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── fundamentals.py               # yfinance P/E, margins, growth
│   │   ├── technical.py                  # RSI, MAs, volume
│   │   ├── sentiment.py                  # Finnhub news sentiment
│   │   └── sec_filings.py               # EDGAR 10-K/10-Q + insider activity
│   ├── tests/
│   │   ├── test_fundamentals.py
│   │   ├── test_technical.py
│   │   ├── test_sentiment.py
│   │   └── test_sec_filings.py
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/                            # Next.js app (deployed to Vercel)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                      # / search page
│   │   ├── research/[ticker]/page.tsx    # research report
│   │   ├── watchlist/page.tsx
│   │   ├── screener/page.tsx
│   │   └── alerts/page.tsx
│   ├── app/api/
│   │   ├── analyze/[ticker]/route.ts     # POST → trigger Trigger.dev task
│   │   ├── research/[ticker]/route.ts    # GET → poll Neon for result
│   │   ├── watchlist/route.ts            # GET + POST watchlist
│   │   ├── watchlist/[ticker]/route.ts   # DELETE watchlist entry
│   │   ├── screener/run/route.ts         # POST → filter research table
│   │   ├── screener/configs/route.ts     # GET + POST screener configs
│   │   ├── alerts/route.ts              # GET + POST alert rules
│   │   └── alerts/[id]/route.ts         # PATCH + DELETE alert rules
│   ├── components/
│   │   ├── AgentCard.tsx                 # score + signals per agent
│   │   ├── ScoreBadge.tsx               # colored 0–10 score badge
│   │   ├── TickerCard.tsx               # watchlist grid card
│   │   └── FilterBuilder.tsx            # screener/alerts filter UI
│   ├── lib/
│   │   └── db.ts                        # Prisma client singleton
│   ├── trigger/
│   │   └── analyze_ticker.ts            # Trigger.dev task (fan-out + synthesis)
│   ├── prisma/
│   │   └── schema.prisma
│   └── package.json
├── scripts/
│   └── run_pipeline.py                  # called by daily_pipeline.yml
├── .env.example
├── .gitignore
└── docker-compose.yml
```

---

### Task 1: GitHub Repo + Root Project Files

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create a public GitHub repo**

```bash
gh repo create alphaagent --public --description "Multi-agent stock research platform"
git remote add origin https://github.com/bsidebot/alphaagent.git
git branch -M main
git push -u origin main
```

Expected: repo created at github.com/bsidebot/alphaagent, design spec commit visible.

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/
.pytest_cache/

# Node
node_modules/
.next/
.turbo/

# Env
.env
.env.local
.env.*.local

# DB
*.db
*.sqlite

# OS
.DS_Store
```

- [ ] **Step 3: Create `.env.example`**

```
# Neon PostgreSQL
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require

# Gemini Flash (free — get key at aistudio.google.com)
GEMINI_API_KEY=

# Finnhub (free — get key at finnhub.io)
FINNHUB_API_KEY=

# FastAPI on Render
FASTAPI_URL=https://alphaagent-fastapi.onrender.com

# Trigger.dev (get from trigger.dev dashboard)
TRIGGER_SECRET_KEY=
TRIGGER_PROJECT_REF=

# Nodemailer (Gmail SMTP — use an App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=your_app_password
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
version: "3.9"
services:
  fastapi:
    build: ./fastapi
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - FINNHUB_API_KEY=${FINNHUB_API_KEY}

  dashboard:
    build: ./dashboard
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - fastapi
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example docker-compose.yml
git commit -m "chore: repo setup — gitignore, env template, docker-compose"
git push
```

---

### Task 2: Neon Database + Prisma Schema

**Files:**
- Create: `dashboard/prisma/schema.prisma`
- Create: `dashboard/package.json` (initial)

- [ ] **Step 1: Create a Neon project**

Go to neon.tech → New Project → name it `alphaagent` → copy the connection string. Add it to a local `.env` file:

```
DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
```

- [ ] **Step 2: Scaffold the Next.js app**

```bash
cd /Users/ben/alphaagent
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir no --import-alias "@/*"
cd dashboard
```

- [ ] **Step 3: Install Prisma and Trigger.dev**

```bash
npm install prisma @prisma/client @trigger.dev/sdk @google/generative-ai nodemailer
npm install -D @types/nodemailer
npx prisma init --datasource-provider postgresql
```

- [ ] **Step 4: Write `dashboard/prisma/schema.prisma`**

Replace the generated schema with:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Research {
  id             String   @id @default(uuid())
  ticker         String
  analyzedAt     DateTime @default(now())
  status         String   // "pending" | "complete" | "error"
  overallScore   Float?
  thesis         String?
  recommendation String?
  fundScore      Float?
  techScore      Float?
  sentScore      Float?
  secScore       Float?
  fundData       Json?
  techData       Json?
  sentData       Json?
  secData        Json?
  errorMsg       String?

  @@index([ticker, analyzedAt(sort: Desc)])
}

model Watchlist {
  id       String   @id @default(uuid())
  ticker   String   @unique
  addedAt  DateTime @default(now())
}

model ScreenerConfig {
  id        String   @id @default(uuid())
  name      String
  filters   Json
  createdAt DateTime @default(now())
}

model AlertRule {
  id            String    @id @default(uuid())
  name          String
  filters       Json
  email         String
  isActive      Boolean   @default(true)
  createdAt     DateTime  @default(now())
  lastTriggered DateTime?
}
```

- [ ] **Step 5: Push schema to Neon**

```bash
cd dashboard
npx prisma db push
```

Expected: `Your database is now in sync with your Prisma schema.`

- [ ] **Step 6: Create `dashboard/lib/db.ts`**

```typescript
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma =
  globalForPrisma.prisma ?? new PrismaClient({ log: ["error"] });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
```

- [ ] **Step 7: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/
git commit -m "feat: Next.js scaffold + Prisma schema pushed to Neon"
git push
```

---

### Task 3: FastAPI Project Skeleton

**Files:**
- Create: `fastapi/requirements.txt`
- Create: `fastapi/main.py`
- Create: `fastapi/agents/__init__.py`
- Create: `fastapi/Dockerfile`

- [ ] **Step 1: Create `fastapi/requirements.txt`**

```
fastapi==0.115.0
uvicorn==0.32.0
yfinance==0.2.50
pandas==2.2.3
numpy==2.1.3
httpx==0.27.2
pytest==8.3.5
pytest-asyncio==0.24.0
httpx==0.27.2
python-dotenv==1.0.1
```

- [ ] **Step 2: Create virtual environment and install**

```bash
cd /Users/ben/alphaagent/fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 3: Create `fastapi/agents/__init__.py`**

```python
```

(empty — marks the directory as a Python package)

- [ ] **Step 4: Create `fastapi/main.py`**

```python
from fastapi import FastAPI
from agents import fundamentals, technical, sentiment, sec_filings

app = FastAPI(title="AlphaAgent FastAPI", version="1.0.0")

app.include_router(fundamentals.router, prefix="/agents")
app.include_router(technical.router, prefix="/agents")
app.include_router(sentiment.router, prefix="/agents")
app.include_router(sec_filings.router, prefix="/agents")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Verify the app starts**

```bash
cd /Users/ben/alphaagent/fastapi
source .venv/bin/activate
uvicorn main:app --reload
```

Expected: `Uvicorn running on http://127.0.0.1:8000`. `GET /health` returns `{"status": "ok"}`.

- [ ] **Step 6: Create `fastapi/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Commit**

```bash
cd /Users/ben/alphaagent
git add fastapi/
git commit -m "feat: FastAPI skeleton with health endpoint"
git push
```

---

### Task 4: Fundamentals Agent

**Files:**
- Create: `fastapi/agents/fundamentals.py`
- Create: `fastapi/tests/test_fundamentals.py`

- [ ] **Step 1: Create `fastapi/tests/test_fundamentals.py`**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


def _mock_info(pe=18.0, margin=0.25, dte=45.0, rev_growth=0.20, eps_growth=0.15):
    return {
        "trailingPE": pe,
        "profitMargins": margin,
        "debtToEquity": dte,
        "revenueGrowth": rev_growth,
        "earningsGrowth": eps_growth,
    }


@patch("agents.fundamentals.yf.Ticker")
def test_fundamentals_returns_score_and_data(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert "signals" in body
    assert "data" in body
    assert 0 <= body["score"] <= 10


@patch("agents.fundamentals.yf.Ticker")
def test_high_quality_company_scores_above_7(mock_ticker):
    mock_ticker.return_value.info = _mock_info(pe=18, margin=0.30, dte=30, rev_growth=0.25, eps_growth=0.20)
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    assert resp.json()["score"] > 7


@patch("agents.fundamentals.yf.Ticker")
def test_negative_margin_scores_below_5(mock_ticker):
    mock_ticker.return_value.info = _mock_info(pe=-1, margin=-0.10, dte=300, rev_growth=-0.05, eps_growth=-0.20)
    resp = client.get("/agents/fundamentals?ticker=BAD")
    assert resp.json()["score"] < 5


@patch("agents.fundamentals.yf.Ticker")
def test_signals_list_is_populated(mock_ticker):
    mock_ticker.return_value.info = _mock_info(margin=0.30, rev_growth=0.25, dte=300)
    resp = client.get("/agents/fundamentals?ticker=AAPL")
    signals = resp.json()["signals"]
    assert isinstance(signals, list)
    assert len(signals) > 0
```

- [ ] **Step 2: Run tests — expect failure**

```bash
cd /Users/ben/alphaagent/fastapi
source .venv/bin/activate
pytest tests/test_fundamentals.py -v
```

Expected: `ModuleNotFoundError` — `agents.fundamentals` doesn't exist yet.

- [ ] **Step 3: Create `fastapi/agents/fundamentals.py`**

```python
from fastapi import APIRouter, HTTPException
import yfinance as yf

router = APIRouter()


@router.get("/fundamentals")
def get_fundamentals(ticker: str):
    try:
        info = yf.Ticker(ticker).info
        pe = info.get("trailingPE")
        margin = info.get("profitMargins")
        dte = info.get("debtToEquity")
        rev_growth = info.get("revenueGrowth")
        eps_growth = info.get("earningsGrowth")

        return {
            "score": _score(pe, margin, dte, rev_growth, eps_growth),
            "signals": _signals(pe, margin, dte, rev_growth, eps_growth),
            "data": {
                "pe_ratio": pe,
                "profit_margin_pct": round(margin * 100, 2) if margin is not None else None,
                "debt_to_equity": dte,
                "revenue_growth_pct": round(rev_growth * 100, 2) if rev_growth is not None else None,
                "eps_growth_pct": round(eps_growth * 100, 2) if eps_growth is not None else None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _score(pe, margin, dte, rev_growth, eps_growth) -> float:
    score = 5.0
    if margin is not None:
        if margin > 0.20:
            score += 1.5
        elif margin > 0.10:
            score += 0.75
        elif margin < 0:
            score -= 2.0
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 1.5
        elif rev_growth > 0.05:
            score += 0.75
        elif rev_growth < 0:
            score -= 1.0
    if dte is not None:
        if dte < 50:
            score += 0.5
        elif dte > 200:
            score -= 1.5
    if pe is not None:
        if pe < 0:
            score -= 1.0
        elif pe < 15:
            score += 0.5
        elif pe > 50:
            score -= 0.5
    return round(max(0.0, min(10.0, score)), 2)


def _signals(pe, margin, dte, rev_growth, eps_growth) -> list[str]:
    out = []
    if margin is not None and margin > 0.20:
        out.append(f"Strong profit margin: {margin*100:.1f}%")
    if margin is not None and margin < 0:
        out.append(f"Negative margin: {margin*100:.1f}%")
    if rev_growth is not None and rev_growth > 0.15:
        out.append(f"Strong revenue growth: {rev_growth*100:.1f}% YoY")
    if rev_growth is not None and rev_growth < 0:
        out.append(f"Revenue declining: {rev_growth*100:.1f}% YoY")
    if dte is not None and dte > 200:
        out.append(f"High leverage: D/E {dte:.0f}%")
    if pe is not None and pe < 0:
        out.append("Negative earnings (P/E N/A)")
    if not out:
        out.append("Fundamentals within normal range")
    return out
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_fundamentals.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add fastapi/agents/fundamentals.py fastapi/tests/test_fundamentals.py
git commit -m "feat: fundamentals agent — P/E, margins, growth scoring"
git push
```

---

### Task 5: Technical Agent

**Files:**
- Create: `fastapi/agents/technical.py`
- Create: `fastapi/tests/test_technical.py`

- [ ] **Step 1: Create `fastapi/tests/test_technical.py`**

```python
import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)


def _make_history(n=250, trend="up"):
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    if trend == "up":
        closes = np.linspace(100, 180, n) + np.random.normal(0, 2, n)
    else:
        closes = np.linspace(180, 100, n) + np.random.normal(0, 2, n)
    volumes = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame({"Close": closes, "High": closes * 1.01, "Volume": volumes}, index=dates)


@patch("agents.technical.yf.Ticker")
def test_technical_returns_score_and_data(mock_ticker):
    mock_ticker.return_value.history.return_value = _make_history()
    resp = client.get("/agents/technical?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert "data" in body
    assert "rsi" in body["data"]
    assert 0 <= body["score"] <= 10


@patch("agents.technical.yf.Ticker")
def test_uptrend_scores_higher_than_downtrend(mock_ticker):
    mock_ticker.return_value.history.return_value = _make_history(trend="up")
    up_score = client.get("/agents/technical?ticker=AAPL").json()["score"]

    mock_ticker.return_value.history.return_value = _make_history(trend="down")
    down_score = client.get("/agents/technical?ticker=AAPL").json()["score"]

    assert up_score > down_score


@patch("agents.technical.yf.Ticker")
def test_empty_history_returns_404(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()
    resp = client.get("/agents/technical?ticker=FAKE")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_technical.py -v
```

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Create `fastapi/agents/technical.py`**

```python
from fastapi import APIRouter, HTTPException
import yfinance as yf
import pandas as pd
import numpy as np

router = APIRouter()


@router.get("/technical")
def get_technical(ticker: str):
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price history for {ticker}")

        closes = hist["Close"]
        rsi = _rsi(closes, 14)
        ma_50 = float(closes.rolling(50).mean().iloc[-1])
        ma_200 = float(closes.rolling(200).mean().iloc[-1])
        price = float(closes.iloc[-1])
        high_52w = float(hist["High"].max())
        avg_vol_20 = float(hist["Volume"].rolling(20).mean().iloc[-1])
        cur_vol = float(hist["Volume"].iloc[-1])
        vol_ratio = cur_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
        pct_from_high = ((price - high_52w) / high_52w) * 100

        return {
            "score": _score(rsi, price, ma_50, ma_200),
            "signals": _signals(rsi, price, ma_50, ma_200, vol_ratio),
            "data": {
                "rsi": round(rsi, 2),
                "ma_50": round(ma_50, 2),
                "ma_200": round(ma_200, 2),
                "current_price": round(price, 2),
                "volume_ratio": round(vol_ratio, 2),
                "price_vs_52w_high_pct": round(pct_from_high, 2),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return float((100 - (100 / (1 + rs))).iloc[-1])


def _score(rsi, price, ma50, ma200) -> float:
    score = 5.0
    if 40 <= rsi <= 60:
        score += 1.0
    elif rsi < 30:
        score += 1.5
    elif rsi > 70:
        score -= 1.0
    if price > ma50:
        score += 1.5
    else:
        score -= 0.5
    if ma50 > ma200:
        score += 1.5
    else:
        score -= 1.0
    return round(max(0.0, min(10.0, score)), 2)


def _signals(rsi, price, ma50, ma200, vol_ratio) -> list[str]:
    out = [f"RSI: {rsi:.1f}"]
    if rsi > 70:
        out.append("Overbought (RSI > 70)")
    elif rsi < 30:
        out.append("Oversold (RSI < 30)")
    out.append("Golden cross (50MA > 200MA)" if ma50 > ma200 else "Death cross (50MA < 200MA)")
    out.append("Price above 50-day MA" if price > ma50 else "Price below 50-day MA")
    if vol_ratio > 1.5:
        out.append(f"High volume: {vol_ratio:.1f}× average")
    return out
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_technical.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add fastapi/agents/technical.py fastapi/tests/test_technical.py
git commit -m "feat: technical agent — RSI, moving averages, volume"
git push
```

---

### Task 6: Sentiment Agent

**Files:**
- Create: `fastapi/agents/sentiment.py`
- Create: `fastapi/tests/test_sentiment.py`

- [ ] **Step 1: Create `fastapi/tests/test_sentiment.py`**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

MOCK_SENTIMENT = {
    "sentiment": {"bullishPercent": 0.75, "bearishPercent": 0.25},
    "buzz": {"articlesInLastWeek": 25},
}

MOCK_NEWS = [
    {"headline": "Apple beats earnings", "datetime": 1700000000},
    {"headline": "iPhone sales strong", "datetime": 1700000001},
]


@patch("agents.sentiment.httpx.get")
def test_sentiment_returns_score_and_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = MOCK_SENTIMENT
        else:
            m.json.return_value = MOCK_NEWS
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert 0 <= body["score"] <= 10
    assert "bullish_pct" in body["data"]


@patch("agents.sentiment.httpx.get")
def test_bullish_sentiment_scores_above_6(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = {"sentiment": {"bullishPercent": 0.80}, "buzz": {"articlesInLastWeek": 10}}
        else:
            m.json.return_value = []
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert resp.json()["score"] > 6


@patch("agents.sentiment.httpx.get")
def test_top_headlines_in_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "news-sentiment" in url:
            m.json.return_value = MOCK_SENTIMENT
        else:
            m.json.return_value = MOCK_NEWS
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sentiment?ticker=AAPL")
    assert isinstance(resp.json()["data"]["top_headlines"], list)
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_sentiment.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `fastapi/agents/sentiment.py`**

```python
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")


@router.get("/sentiment")
def get_sentiment(ticker: str):
    try:
        sent = httpx.get(
            "https://finnhub.io/api/v1/news-sentiment",
            params={"symbol": ticker, "token": FINNHUB_KEY},
            timeout=10,
        ).json()

        to_d = datetime.now().strftime("%Y-%m-%d")
        from_d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        news = httpx.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": from_d, "to": to_d, "token": FINNHUB_KEY},
            timeout=10,
        ).json()

        bullish_pct = sent.get("sentiment", {}).get("bullishPercent", 0.5) * 100
        bearish_pct = 100 - bullish_pct
        article_count = sent.get("buzz", {}).get("articlesInLastWeek", 0)
        finnhub_score = bullish_pct / 100
        score = round(finnhub_score * 10, 2)

        headlines = [
            {"headline": a.get("headline", ""), "datetime": a.get("datetime", 0)}
            for a in (news[:5] if isinstance(news, list) else [])
        ]

        signals = []
        if bullish_pct > 65:
            signals.append(f"Strongly bullish: {bullish_pct:.0f}% positive news")
        elif bullish_pct > 50:
            signals.append(f"Mildly bullish: {bullish_pct:.0f}% positive")
        elif bearish_pct > 65:
            signals.append(f"Strongly bearish: {bearish_pct:.0f}% negative news")
        else:
            signals.append(f"Mixed sentiment: {bullish_pct:.0f}% bullish")
        if article_count > 20:
            signals.append(f"High media buzz: {article_count} articles this week")

        return {
            "score": score,
            "signals": signals,
            "data": {
                "article_count": article_count,
                "bullish_pct": round(bullish_pct, 1),
                "bearish_pct": round(bearish_pct, 1),
                "finnhub_score": round(finnhub_score, 3),
                "top_headlines": headlines,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_sentiment.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add fastapi/agents/sentiment.py fastapi/tests/test_sentiment.py
git commit -m "feat: sentiment agent — Finnhub news sentiment scoring"
git push
```

---

### Task 7: SEC Filings Agent

**Files:**
- Create: `fastapi/agents/sec_filings.py`
- Create: `fastapi/tests/test_sec_filings.py`

- [ ] **Step 1: Create `fastapi/tests/test_sec_filings.py`**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app

client = TestClient(app)

MOCK_TICKERS = {
    "0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}
}

MOCK_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "4", "4"],
            "filingDate": ["2024-11-01", "2024-08-01", "2024-10-15", "2024-09-15"],
            "accessionNumber": ["0000320193-24-000123", "0000320193-24-000456", "x", "x"],
        }
    }
}


@patch("agents.sec_filings.httpx.get")
def test_sec_returns_score_and_data(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "company_tickers" in url:
            m.json.return_value = MOCK_TICKERS
        elif "submissions" in url:
            m.json.return_value = MOCK_SUBMISSIONS
        else:
            m.text = "Annual report with no issues."
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sec_filings?ticker=AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert "score" in body
    assert 0 <= body["score"] <= 10
    assert "last_10k_date" in body["data"]


@patch("agents.sec_filings.httpx.get")
def test_red_flags_lower_score(mock_get):
    def side_effect(url, **kwargs):
        m = MagicMock()
        if "company_tickers" in url:
            m.json.return_value = MOCK_TICKERS
        elif "submissions" in url:
            m.json.return_value = MOCK_SUBMISSIONS
        else:
            m.text = "going concern material weakness guidance withdrawn"
        return m
    mock_get.side_effect = side_effect

    resp = client.get("/agents/sec_filings?ticker=AAPL")
    assert resp.json()["score"] < 5


@patch("agents.sec_filings.httpx.get")
def test_unknown_ticker_returns_404(mock_get):
    m = MagicMock()
    m.json.return_value = {}
    mock_get.return_value = m

    resp = client.get("/agents/sec_filings?ticker=ZZZZ")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests — expect failure**

```bash
pytest tests/test_sec_filings.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `fastapi/agents/sec_filings.py`**

```python
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

RED_FLAG_PHRASES = ["going concern", "material weakness", "guidance withdrawn", "restatement"]
HEADERS = {"User-Agent": "AlphaAgent research@alphaagent.dev"}


@router.get("/sec_filings")
def get_sec_filings(ticker: str):
    try:
        cik = _get_cik(ticker)
        if not cik:
            raise HTTPException(status_code=404, detail=f"CIK not found for {ticker}")

        filings = _get_recent_filings(cik)
        last_10k = next((f for f in filings if f["form"] == "10-K"), None)
        last_10q = next((f for f in filings if f["form"] == "10-Q"), None)
        form4_count = sum(1 for f in filings if f["form"] == "4")

        red_flags = []
        if last_10k:
            red_flags = _scan_red_flags(cik, last_10k["accessionNumber"])

        # Form 4 count as rough insider activity proxy (positive = active insider buying/selling)
        insider_net = form4_count

        return {
            "score": _score(red_flags, insider_net),
            "signals": _signals(red_flags, insider_net, last_10k, last_10q),
            "data": {
                "last_10k_date": last_10k["filingDate"] if last_10k else None,
                "last_10q_date": last_10q["filingDate"] if last_10q else None,
                "red_flags": red_flags,
                "insider_net_shares": insider_net,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_cik(ticker: str) -> str | None:
    data = httpx.get(
        "https://www.sec.gov/files/company_tickers.json",
        timeout=10,
        headers=HEADERS,
    ).json()
    for _, co in data.items():
        if co.get("ticker", "").upper() == ticker.upper():
            return str(co["cik_str"]).zfill(10)
    return None


def _get_recent_filings(cik: str) -> list[dict]:
    data = httpx.get(
        f"https://data.sec.gov/submissions/CIK{cik}.json",
        timeout=10,
        headers=HEADERS,
    ).json()
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    return [
        {"form": f, "filingDate": d, "accessionNumber": a}
        for f, d, a in zip(forms, dates, accs)
        if f in ("10-K", "10-Q", "4")
    ][:20]


def _scan_red_flags(cik: str, accession: str) -> list[str]:
    try:
        acc_clean = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{accession}-index.htm"
        text = httpx.get(url, timeout=15, headers=HEADERS).text.lower()
        return [phrase for phrase in RED_FLAG_PHRASES if phrase in text]
    except Exception:
        return []


def _score(red_flags: list, form4_count: int) -> float:
    score = 7.0
    score -= len(red_flags) * 2.0
    if form4_count > 5:
        score += 0.5
    return round(max(0.0, min(10.0, score)), 2)


def _signals(red_flags, form4_count, last_10k, last_10q) -> list[str]:
    out = []
    if red_flags:
        for flag in red_flags:
            out.append(f"Red flag: '{flag}'")
    else:
        out.append("No red flags in recent filings")
    if last_10k:
        out.append(f"Most recent 10-K: {last_10k['filingDate']}")
    if last_10q:
        out.append(f"Most recent 10-Q: {last_10q['filingDate']}")
    if form4_count > 3:
        out.append(f"Active insider transactions: {form4_count} Form 4s recently")
    return out
```

- [ ] **Step 4: Run all FastAPI tests**

```bash
cd /Users/ben/alphaagent/fastapi
pytest tests/ -v
```

Expected: all tests pass (fundamentals + technical + sentiment + sec_filings).

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add fastapi/agents/sec_filings.py fastapi/tests/test_sec_filings.py
git commit -m "feat: SEC filings agent — EDGAR 10-K/10-Q red flag detection"
git push
```

---

### Task 8: Deploy FastAPI to Render

**Files:** none (deployment configuration via Render dashboard)

- [ ] **Step 1: Sign up for Render and deploy**

1. Go to render.com → New → Web Service
2. Connect your GitHub repo `bsidebot/alphaagent`
3. Settings:
   - **Root directory:** `fastapi`
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable: `FINNHUB_API_KEY=<your key>`
5. Click Deploy

Expected: service URL like `https://alphaagent-fastapi.onrender.com`

- [ ] **Step 2: Verify the deployed health endpoint**

```bash
curl https://alphaagent-fastapi.onrender.com/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Test a live agent endpoint**

```bash
curl "https://alphaagent-fastapi.onrender.com/agents/fundamentals?ticker=AAPL"
```

Expected: JSON with `score`, `signals`, and `data` fields. (May take 30s first call — Render free tier cold start.)

- [ ] **Step 4: Add the Render URL to your local `.env`**

```
FASTAPI_URL=https://alphaagent-fastapi.onrender.com
```

---

### Task 9: Trigger.dev Task — analyze_ticker

**Files:**
- Create: `dashboard/trigger/analyze_ticker.ts`
- Modify: `dashboard/package.json` (add trigger.dev scripts)

- [ ] **Step 1: Initialize Trigger.dev in the dashboard**

```bash
cd /Users/ben/alphaagent/dashboard
npx trigger.dev@latest init
```

Follow the prompts: select your project or create a new one called `alphaagent`. This creates `trigger.config.ts` and updates `package.json`.

- [ ] **Step 2: Create `dashboard/trigger/analyze_ticker.ts`**

```typescript
import { task } from "@trigger.dev/sdk/v3";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { prisma } from "../lib/db";

const genai = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const FASTAPI_URL = process.env.FASTAPI_URL!;

interface AgentOutput {
  score: number;
  signals: string[];
  data: Record<string, unknown>;
}

export const analyzeTicker = task({
  id: "analyze-ticker",
  maxDuration: 120,
  run: async (payload: { ticker: string; researchId: string }) => {
    const { ticker, researchId } = payload;

    try {
      const [fund, tech, sent, sec] = await Promise.all([
        fetch(`${FASTAPI_URL}/agents/fundamentals?ticker=${ticker}`).then((r) =>
          r.json() as Promise<AgentOutput>
        ),
        fetch(`${FASTAPI_URL}/agents/technical?ticker=${ticker}`).then((r) =>
          r.json() as Promise<AgentOutput>
        ),
        fetch(`${FASTAPI_URL}/agents/sentiment?ticker=${ticker}`).then((r) =>
          r.json() as Promise<AgentOutput>
        ),
        fetch(`${FASTAPI_URL}/agents/sec_filings?ticker=${ticker}`).then((r) =>
          r.json() as Promise<AgentOutput>
        ),
      ]);

      const overallScore =
        fund.score * 0.3 +
        tech.score * 0.25 +
        sent.score * 0.25 +
        sec.score * 0.2;

      const { thesis, recommendation } = await _synthesize(
        ticker,
        fund,
        tech,
        sent,
        sec,
        overallScore
      );

      await prisma.research.update({
        where: { id: researchId },
        data: {
          status: "complete",
          overallScore: Math.round(overallScore * 100) / 100,
          thesis,
          recommendation,
          fundScore: fund.score,
          techScore: tech.score,
          sentScore: sent.score,
          secScore: sec.score,
          fundData: fund.data,
          techData: tech.data,
          sentData: sent.data,
          secData: sec.data,
        },
      });
    } catch (err) {
      await prisma.research.update({
        where: { id: researchId },
        data: { status: "error", errorMsg: String(err) },
      });
      throw err;
    }
  },
});

async function _synthesize(
  ticker: string,
  fund: AgentOutput,
  tech: AgentOutput,
  sent: AgentOutput,
  sec: AgentOutput,
  overallScore: number
): Promise<{ thesis: string; recommendation: string }> {
  const model = genai.getGenerativeModel({ model: "gemini-1.5-flash" });
  const prompt = `You are a financial analyst. Write a 2-3 paragraph investment thesis for ${ticker} based on these agent outputs.

Fundamentals (score ${fund.score}/10): ${JSON.stringify(fund.data)}
Signals: ${fund.signals.join(", ")}

Technical (score ${tech.score}/10): ${JSON.stringify(tech.data)}
Signals: ${tech.signals.join(", ")}

Sentiment (score ${sent.score}/10): ${JSON.stringify(sent.data)}
Signals: ${sent.signals.join(", ")}

SEC Filings (score ${sec.score}/10): ${JSON.stringify(sec.data)}
Signals: ${sec.signals.join(", ")}

Overall score: ${overallScore.toFixed(1)}/10

Respond with valid JSON only (no markdown):
{"thesis": "...", "recommendation": "bullish" | "neutral" | "bearish"}`;

  const result = await model.generateContent(prompt);
  const text = result.response.text().trim();

  try {
    const parsed = JSON.parse(text);
    const rec = ["bullish", "neutral", "bearish"].includes(parsed.recommendation)
      ? parsed.recommendation
      : "neutral";
    return { thesis: parsed.thesis ?? text, recommendation: rec };
  } catch {
    return { thesis: text, recommendation: "neutral" };
  }
}
```

- [ ] **Step 3: Deploy the Trigger.dev task**

```bash
cd /Users/ben/alphaagent/dashboard
npx trigger.dev@latest deploy
```

Expected: task `analyze-ticker` appears in your Trigger.dev dashboard.

- [ ] **Step 4: Add Trigger.dev env vars to your local `.env`**

Copy `TRIGGER_SECRET_KEY` and `TRIGGER_PROJECT_REF` from the Trigger.dev dashboard into `.env`.

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/trigger/ dashboard/trigger.config.ts
git commit -m "feat: Trigger.dev analyze-ticker task — parallel fan-out + Gemini synthesis"
git push
```

---

### Task 10: Next.js API Routes

**Files:**
- Create: `dashboard/app/api/analyze/[ticker]/route.ts`
- Create: `dashboard/app/api/research/[ticker]/route.ts`
- Create: `dashboard/app/api/watchlist/route.ts`
- Create: `dashboard/app/api/watchlist/[ticker]/route.ts`
- Create: `dashboard/app/api/screener/run/route.ts`
- Create: `dashboard/app/api/screener/configs/route.ts`
- Create: `dashboard/app/api/alerts/route.ts`
- Create: `dashboard/app/api/alerts/[id]/route.ts`

- [ ] **Step 1: Create `dashboard/app/api/analyze/[ticker]/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { tasks } from "@trigger.dev/sdk/v3";
import { prisma } from "@/lib/db";
import type { analyzeTicker } from "@/trigger/analyze_ticker";

const FRESH_HOURS = 6;

export async function POST(
  _req: NextRequest,
  { params }: { params: { ticker: string } }
) {
  const ticker = params.ticker.toUpperCase();

  // Return cached result if fresh
  const existing = await prisma.research.findFirst({
    where: { ticker, status: "complete" },
    orderBy: { analyzedAt: "desc" },
  });

  if (existing) {
    const ageHours =
      (Date.now() - existing.analyzedAt.getTime()) / (1000 * 60 * 60);
    if (ageHours < FRESH_HOURS) {
      return NextResponse.json({ id: existing.id, status: "complete" });
    }
  }

  // Create pending row and trigger task
  const research = await prisma.research.create({
    data: { ticker, status: "pending" },
  });

  await tasks.trigger<typeof analyzeTicker>("analyze-ticker", {
    ticker,
    researchId: research.id,
  });

  return NextResponse.json({ id: research.id, status: "pending" });
}
```

- [ ] **Step 2: Create `dashboard/app/api/research/[ticker]/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET(
  _req: NextRequest,
  { params }: { params: { ticker: string } }
) {
  const ticker = params.ticker.toUpperCase();
  const research = await prisma.research.findFirst({
    where: { ticker },
    orderBy: { analyzedAt: "desc" },
  });

  if (!research) return NextResponse.json(null);
  return NextResponse.json(research);
}
```

- [ ] **Step 3: Create `dashboard/app/api/watchlist/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  const watchlist = await prisma.watchlist.findMany({
    orderBy: { addedAt: "desc" },
  });

  // Attach latest research score for each ticker
  const tickers = watchlist.map((w) => w.ticker);
  const research = await prisma.research.findMany({
    where: { ticker: { in: tickers }, status: "complete" },
    orderBy: { analyzedAt: "desc" },
    distinct: ["ticker"],
  });

  const researchMap = Object.fromEntries(research.map((r) => [r.ticker, r]));
  const result = watchlist.map((w) => ({
    ...w,
    research: researchMap[w.ticker] ?? null,
  }));

  return NextResponse.json(result);
}

export async function POST(req: NextRequest) {
  const { ticker } = await req.json();
  if (!ticker) return NextResponse.json({ error: "ticker required" }, { status: 400 });

  const entry = await prisma.watchlist.upsert({
    where: { ticker: ticker.toUpperCase() },
    update: {},
    create: { ticker: ticker.toUpperCase() },
  });
  return NextResponse.json(entry);
}
```

- [ ] **Step 4: Create `dashboard/app/api/watchlist/[ticker]/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { ticker: string } }
) {
  await prisma.watchlist.delete({
    where: { ticker: params.ticker.toUpperCase() },
  });
  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 5: Create `dashboard/app/api/screener/run/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

interface Filter {
  field: string;
  operator: ">" | "<" | "=";
  value: number;
}

const SCALAR_FIELDS = new Set([
  "overallScore", "fundScore", "techScore", "sentScore", "secScore",
]);

export async function POST(req: NextRequest) {
  const { filters }: { filters: Filter[] } = await req.json();

  // Get all complete research rows (latest per ticker)
  const all = await prisma.research.findMany({
    where: { status: "complete" },
    orderBy: { analyzedAt: "desc" },
    distinct: ["ticker"],
  });

  const results = all.filter((row) =>
    filters.every((f) => {
      let val: number | null = null;
      if (SCALAR_FIELDS.has(f.field)) {
        val = (row as Record<string, unknown>)[f.field] as number | null;
      } else {
        // Try jsonb data fields
        const dataFields = ["fundData", "techData", "sentData", "secData"];
        for (const df of dataFields) {
          const data = (row as Record<string, unknown>)[df] as Record<string, unknown> | null;
          if (data && f.field in data) {
            val = data[f.field] as number;
            break;
          }
        }
      }
      if (val === null) return false;
      if (f.operator === ">") return val > f.value;
      if (f.operator === "<") return val < f.value;
      return val === f.value;
    })
  );

  return NextResponse.json(results);
}
```

- [ ] **Step 6: Create `dashboard/app/api/screener/configs/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  return NextResponse.json(await prisma.screenerConfig.findMany({ orderBy: { createdAt: "desc" } }));
}

export async function POST(req: NextRequest) {
  const { name, filters } = await req.json();
  const config = await prisma.screenerConfig.create({ data: { name, filters } });
  return NextResponse.json(config);
}
```

- [ ] **Step 7: Create `dashboard/app/api/alerts/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  return NextResponse.json(await prisma.alertRule.findMany({ orderBy: { createdAt: "desc" } }));
}

export async function POST(req: NextRequest) {
  const { name, filters, email } = await req.json();
  const rule = await prisma.alertRule.create({ data: { name, filters, email } });
  return NextResponse.json(rule);
}
```

- [ ] **Step 8: Create `dashboard/app/api/alerts/[id]/route.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const body = await req.json();
  const data: { isActive?: boolean; lastTriggered?: Date } = {};
  if (typeof body.isActive === "boolean") data.isActive = body.isActive;
  if (body.lastTriggered === "now") data.lastTriggered = new Date();

  const rule = await prisma.alertRule.update({
    where: { id: params.id },
    data,
  });
  return NextResponse.json(rule);
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  await prisma.alertRule.delete({ where: { id: params.id } });
  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 9: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/api/
git commit -m "feat: Next.js API routes — analyze, research, watchlist, screener, alerts"
git push
```

---

### Task 11: Shared Components

**Files:**
- Create: `dashboard/components/ScoreBadge.tsx`
- Create: `dashboard/components/AgentCard.tsx`
- Create: `dashboard/components/TickerCard.tsx`
- Create: `dashboard/components/FilterBuilder.tsx`

- [ ] **Step 1: Create `dashboard/components/ScoreBadge.tsx`**

```tsx
interface Props {
  score: number | null;
  size?: "sm" | "lg";
}

export function ScoreBadge({ score, size = "sm" }: Props) {
  if (score === null) return <span className="text-gray-400">—</span>;

  const color =
    score >= 7 ? "bg-green-100 text-green-800 border-green-200"
    : score >= 4 ? "bg-yellow-100 text-yellow-800 border-yellow-200"
    : "bg-red-100 text-red-800 border-red-200";

  const sizeClass = size === "lg" ? "text-3xl px-4 py-2" : "text-sm px-2 py-0.5";

  return (
    <span className={`font-bold rounded border ${color} ${sizeClass}`}>
      {score.toFixed(1)}
    </span>
  );
}
```

- [ ] **Step 2: Create `dashboard/components/AgentCard.tsx`**

```tsx
import { ScoreBadge } from "./ScoreBadge";

interface Props {
  name: string;
  score: number | null;
  signals: string[];
  data: Record<string, unknown> | null;
}

export function AgentCard({ name, score, signals, data }: Props) {
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">{name}</h3>
        <ScoreBadge score={score} />
      </div>
      <ul className="space-y-1">
        {signals.map((s, i) => (
          <li key={i} className="text-sm text-gray-600">
            • {s}
          </li>
        ))}
      </ul>
      {data && (
        <details className="text-xs text-gray-400">
          <summary className="cursor-pointer hover:text-gray-600">Raw data</summary>
          <pre className="mt-2 overflow-auto bg-gray-50 p-2 rounded text-xs">
            {JSON.stringify(data, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `dashboard/components/TickerCard.tsx`**

```tsx
import Link from "next/link";
import { ScoreBadge } from "./ScoreBadge";

interface Props {
  ticker: string;
  overallScore: number | null;
  recommendation: string | null;
}

export function TickerCard({ ticker, overallScore, recommendation }: Props) {
  return (
    <Link href={`/research/${ticker}`}>
      <div className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-bold text-lg">{ticker}</span>
          <ScoreBadge score={overallScore} />
        </div>
        {recommendation && (
          <span
            className={`text-xs font-medium uppercase ${
              recommendation === "bullish"
                ? "text-green-600"
                : recommendation === "bearish"
                ? "text-red-600"
                : "text-yellow-600"
            }`}
          >
            {recommendation}
          </span>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Create `dashboard/components/FilterBuilder.tsx`**

```tsx
"use client";
import { useState } from "react";

const FIELDS = [
  "overallScore", "fundScore", "techScore", "sentScore", "secScore",
  "pe_ratio", "rsi", "debt_to_equity", "revenue_growth_pct", "profit_margin_pct",
];

export interface Filter {
  field: string;
  operator: ">" | "<" | "=";
  value: number;
}

interface Props {
  filters: Filter[];
  onChange: (filters: Filter[]) => void;
}

export function FilterBuilder({ filters, onChange }: Props) {
  const add = () =>
    onChange([...filters, { field: "overallScore", operator: ">", value: 7 }]);

  const remove = (i: number) => onChange(filters.filter((_, idx) => idx !== i));

  const update = (i: number, patch: Partial<Filter>) => {
    const next = [...filters];
    next[i] = { ...next[i], ...patch };
    onChange(next);
  };

  return (
    <div className="space-y-2">
      {filters.map((f, i) => (
        <div key={i} className="flex items-center gap-2">
          <select
            value={f.field}
            onChange={(e) => update(i, { field: e.target.value })}
            className="border rounded px-2 py-1 text-sm"
          >
            {FIELDS.map((field) => (
              <option key={field} value={field}>{field}</option>
            ))}
          </select>
          <select
            value={f.operator}
            onChange={(e) => update(i, { operator: e.target.value as Filter["operator"] })}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value=">">{">"}</option>
            <option value="<">{"<"}</option>
            <option value="=">=</option>
          </select>
          <input
            type="number"
            value={f.value}
            onChange={(e) => update(i, { value: Number(e.target.value) })}
            className="border rounded px-2 py-1 text-sm w-20"
          />
          <button onClick={() => remove(i)} className="text-red-500 text-sm">✕</button>
        </div>
      ))}
      <button
        onClick={add}
        className="text-sm text-blue-600 hover:underline"
      >
        + Add filter
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/components/
git commit -m "feat: shared components — ScoreBadge, AgentCard, TickerCard, FilterBuilder"
git push
```

---

### Task 12: Search Page (`/`)

**Files:**
- Modify: `dashboard/app/page.tsx`

- [ ] **Step 1: Write `dashboard/app/page.tsx`**

```tsx
"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TickerCard } from "@/components/TickerCard";

export default function SearchPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const router = useRouter();

  useEffect(() => {
    fetch("/api/watchlist").then((r) => r.json()).then(setWatchlist);
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const ticker = input.trim().toUpperCase();
    if (!ticker) return;
    setLoading(true);
    setStatus("Starting analysis…");

    const res = await fetch(`/api/analyze/${ticker}`, { method: "POST" });
    const { id, status: initialStatus } = await res.json();

    if (initialStatus === "complete") {
      router.push(`/research/${ticker}`);
      return;
    }

    // Poll until complete
    const steps = ["Fetching fundamentals…", "Running technical analysis…", "Scoring sentiment…", "Parsing SEC filings…", "Synthesizing thesis…"];
    let step = 0;
    const interval = setInterval(async () => {
      setStatus(steps[step % steps.length]);
      step++;

      const poll = await fetch(`/api/research/${ticker}`).then((r) => r.json());
      if (poll?.status === "complete") {
        clearInterval(interval);
        router.push(`/research/${ticker}`);
      } else if (poll?.status === "error") {
        clearInterval(interval);
        setStatus("Analysis failed. Please try again.");
        setLoading(false);
      }
    }, 2000);
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-12 space-y-10">
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold">AlphaAgent</h1>
        <p className="text-gray-500">Multi-agent stock research platform</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md mx-auto">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter ticker (e.g. AAPL)"
          className="flex-1 border rounded-lg px-4 py-2 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "…" : "Analyze"}
        </button>
      </form>

      {status && <p className="text-center text-gray-500 animate-pulse">{status}</p>}

      {watchlist.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-semibold text-gray-700">Watchlist</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {watchlist.map((w) => (
              <TickerCard
                key={w.ticker}
                ticker={w.ticker}
                overallScore={w.research?.overallScore ?? null}
                recommendation={w.research?.recommendation ?? null}
              />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/page.tsx
git commit -m "feat: search page with polling and watchlist grid"
git push
```

---

### Task 13: Research Report Page

**Files:**
- Create: `dashboard/app/research/[ticker]/page.tsx`

- [ ] **Step 1: Create `dashboard/app/research/[ticker]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { ScoreBadge } from "@/components/ScoreBadge";
import { AgentCard } from "@/components/AgentCard";

interface Props {
  params: { ticker: string };
}

export default async function ResearchPage({ params }: Props) {
  const ticker = params.ticker.toUpperCase();
  const research = await prisma.research.findFirst({
    where: { ticker, status: "complete" },
    orderBy: { analyzedAt: "desc" },
  });

  if (!research) notFound();

  const recColor =
    research.recommendation === "bullish"
      ? "text-green-600"
      : research.recommendation === "bearish"
      ? "text-red-600"
      : "text-yellow-600";

  async function addToWatchlist() {
    "use server";
    await fetch(`${process.env.NEXTAUTH_URL ?? "http://localhost:3000"}/api/watchlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">{ticker}</h1>
          <p className={`text-lg font-semibold uppercase ${recColor}`}>
            {research.recommendation ?? "—"}
          </p>
          <p className="text-xs text-gray-400">
            Analyzed {new Date(research.analyzedAt).toLocaleString()}
          </p>
        </div>
        <div className="text-right space-y-2">
          <ScoreBadge score={research.overallScore} size="lg" />
          <form action={addToWatchlist}>
            <button
              type="submit"
              className="text-sm text-blue-600 border border-blue-600 rounded px-3 py-1 hover:bg-blue-50"
            >
              + Watchlist
            </button>
          </form>
        </div>
      </div>

      {research.thesis && (
        <section className="border rounded-lg p-5 bg-gray-50 space-y-2">
          <h2 className="font-semibold">Investment Thesis</h2>
          <p className="text-gray-700 leading-relaxed whitespace-pre-line">{research.thesis}</p>
        </section>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <AgentCard
          name="Fundamentals"
          score={research.fundScore}
          signals={(research.fundData as any)?.signals ?? []}
          data={research.fundData as Record<string, unknown>}
        />
        <AgentCard
          name="Technical"
          score={research.techScore}
          signals={(research.techData as any)?.signals ?? []}
          data={research.techData as Record<string, unknown>}
        />
        <AgentCard
          name="Sentiment"
          score={research.sentScore}
          signals={(research.sentData as any)?.signals ?? []}
          data={research.sentData as Record<string, unknown>}
        />
        <AgentCard
          name="SEC Filings"
          score={research.secScore}
          signals={(research.secData as any)?.signals ?? []}
          data={research.secData as Record<string, unknown>}
        />
      </div>
    </main>
  );
}
```

Note: the `signals` field is inside the agent response at API call time but is stored in the `*Data` jsonb. Update the Trigger.dev task in Task 9 to also store `signals` alongside `data` in the jsonb blob:

```typescript
// In analyze_ticker.ts, update the prisma.research.update data block:
fundData: { ...fund.data, signals: fund.signals },
techData: { ...tech.data, signals: tech.signals },
sentData: { ...sent.data, signals: sent.signals },
secData: { ...sec.data, signals: sec.signals },
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/research/ dashboard/trigger/analyze_ticker.ts
git commit -m "feat: research report page — thesis, scores, agent cards"
git push
```

---

### Task 14: Watchlist Page

**Files:**
- Create: `dashboard/app/watchlist/page.tsx`

- [ ] **Step 1: Create `dashboard/app/watchlist/page.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ScoreBadge } from "@/components/ScoreBadge";

export default function WatchlistPage() {
  const [items, setItems] = useState<any[]>([]);
  const [newTicker, setNewTicker] = useState("");

  const load = () =>
    fetch("/api/watchlist").then((r) => r.json()).then(setItems);

  useEffect(() => { load(); }, []);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    await fetch("/api/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: newTicker }),
    });
    setNewTicker("");
    load();
  };

  const remove = async (ticker: string) => {
    await fetch(`/api/watchlist/${ticker}`, { method: "DELETE" });
    load();
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-6">
      <h1 className="text-2xl font-bold">Watchlist</h1>

      <form onSubmit={add} className="flex gap-2">
        <input
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          placeholder="Add ticker…"
          className="border rounded px-3 py-1.5 text-sm"
        />
        <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm">
          Add
        </button>
      </form>

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-2">Ticker</th>
            <th className="pb-2">Score</th>
            <th className="pb-2">Fund</th>
            <th className="pb-2">Tech</th>
            <th className="pb-2">Sent</th>
            <th className="pb-2">SEC</th>
            <th className="pb-2">Last Analyzed</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.ticker} className="border-b hover:bg-gray-50">
              <td className="py-2">
                <Link href={`/research/${item.ticker}`} className="font-semibold text-blue-600 hover:underline">
                  {item.ticker}
                </Link>
              </td>
              <td><ScoreBadge score={item.research?.overallScore ?? null} /></td>
              <td><ScoreBadge score={item.research?.fundScore ?? null} /></td>
              <td><ScoreBadge score={item.research?.techScore ?? null} /></td>
              <td><ScoreBadge score={item.research?.sentScore ?? null} /></td>
              <td><ScoreBadge score={item.research?.secScore ?? null} /></td>
              <td className="text-gray-400">
                {item.research ? new Date(item.research.analyzedAt).toLocaleDateString() : "—"}
              </td>
              <td>
                <button onClick={() => remove(item.ticker)} className="text-red-400 hover:text-red-600 text-xs">
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/watchlist/
git commit -m "feat: watchlist page — add/remove tickers, score table"
git push
```

---

### Task 15: Screener Page

**Files:**
- Create: `dashboard/app/screener/page.tsx`

- [ ] **Step 1: Create `dashboard/app/screener/page.tsx`**

```tsx
"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { FilterBuilder, Filter } from "@/components/FilterBuilder";
import { ScoreBadge } from "@/components/ScoreBadge";

export default function ScreenerPage() {
  const [filters, setFilters] = useState<Filter[]>([{ field: "overallScore", operator: ">", value: 7 }]);
  const [results, setResults] = useState<any[]>([]);
  const [configs, setConfigs] = useState<any[]>([]);
  const [saveName, setSaveName] = useState("");

  useEffect(() => {
    fetch("/api/screener/configs").then((r) => r.json()).then(setConfigs);
  }, []);

  const run = async () => {
    const res = await fetch("/api/screener/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filters }),
    });
    setResults(await res.json());
  };

  const save = async () => {
    if (!saveName) return;
    await fetch("/api/screener/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: saveName, filters }),
    });
    setSaveName("");
    fetch("/api/screener/configs").then((r) => r.json()).then(setConfigs);
  };

  const loadConfig = (config: any) => setFilters(config.filters);

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-6">
      <h1 className="text-2xl font-bold">Screener</h1>

      {configs.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {configs.map((c) => (
            <button
              key={c.id}
              onClick={() => loadConfig(c)}
              className="border rounded px-3 py-1 text-sm hover:bg-gray-50"
            >
              {c.name}
            </button>
          ))}
        </div>
      )}

      <FilterBuilder filters={filters} onChange={setFilters} />

      <div className="flex gap-2 items-center">
        <button onClick={run} className="bg-blue-600 text-white px-4 py-2 rounded text-sm">
          Run Screener
        </button>
        <input
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          placeholder="Save as…"
          className="border rounded px-3 py-1.5 text-sm"
        />
        <button onClick={save} className="border rounded px-3 py-1.5 text-sm hover:bg-gray-50">
          Save
        </button>
      </div>

      {results.length > 0 && (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="pb-2">Ticker</th>
              <th className="pb-2">Score</th>
              <th className="pb-2">Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.id} className="border-b hover:bg-gray-50">
                <td className="py-2">
                  <Link href={`/research/${r.ticker}`} className="font-semibold text-blue-600 hover:underline">
                    {r.ticker}
                  </Link>
                </td>
                <td><ScoreBadge score={r.overallScore} /></td>
                <td className="capitalize text-gray-600">{r.recommendation ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {results.length === 0 && (
        <p className="text-gray-400 text-sm">No results yet — run the screener above.</p>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/screener/
git commit -m "feat: screener page — filter builder, saved configs, results table"
git push
```

---

### Task 16: Alerts Page

**Files:**
- Create: `dashboard/app/alerts/page.tsx`

- [ ] **Step 1: Create `dashboard/app/alerts/page.tsx`**

```tsx
"use client";
import { useState, useEffect } from "react";
import { FilterBuilder, Filter } from "@/components/FilterBuilder";

export default function AlertsPage() {
  const [rules, setRules] = useState<any[]>([]);
  const [filters, setFilters] = useState<Filter[]>([{ field: "overallScore", operator: ">", value: 8 }]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const load = () =>
    fetch("/api/alerts").then((r) => r.json()).then(setRules);

  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    await fetch("/api/alerts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, filters, email }),
    });
    setName(""); setEmail("");
    load();
  };

  const toggle = async (id: string, isActive: boolean) => {
    await fetch(`/api/alerts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isActive: !isActive }),
    });
    load();
  };

  const remove = async (id: string) => {
    await fetch(`/api/alerts/${id}`, { method: "DELETE" });
    load();
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-8">
      <h1 className="text-2xl font-bold">Alerts</h1>

      <section className="border rounded-lg p-5 space-y-4">
        <h2 className="font-semibold">Create Alert</h2>
        <form onSubmit={create} className="space-y-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Alert name"
            required
            className="border rounded px-3 py-1.5 text-sm w-full"
          />
          <FilterBuilder filters={filters} onChange={setFilters} />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Notify email"
            required
            className="border rounded px-3 py-1.5 text-sm w-full"
          />
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded text-sm">
            Create Alert
          </button>
        </form>
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Active Rules</h2>
        {rules.length === 0 && <p className="text-gray-400 text-sm">No alert rules yet.</p>}
        {rules.map((r) => (
          <div key={r.id} className="border rounded-lg p-4 flex items-start justify-between gap-4">
            <div className="space-y-1">
              <p className="font-medium">{r.name}</p>
              <p className="text-xs text-gray-500">{r.email}</p>
              {r.lastTriggered && (
                <p className="text-xs text-gray-400">
                  Last triggered: {new Date(r.lastTriggered).toLocaleString()}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => toggle(r.id, r.isActive)}
                className={`text-xs px-2 py-1 rounded border ${r.isActive ? "text-green-700 border-green-300 bg-green-50" : "text-gray-500 border-gray-200"}`}
              >
                {r.isActive ? "Active" : "Paused"}
              </button>
              <button onClick={() => remove(r.id)} className="text-red-400 hover:text-red-600 text-xs">
                Delete
              </button>
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/alerts/
git commit -m "feat: alerts page — create email alert rules, toggle, delete"
git push
```

---

### Task 17: Navigation Layout

**Files:**
- Modify: `dashboard/app/layout.tsx`

- [ ] **Step 1: Update `dashboard/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AlphaAgent",
  description: "Multi-agent stock research platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="border-b px-4 py-3 flex items-center gap-6">
          <Link href="/" className="font-bold text-lg">AlphaAgent</Link>
          <Link href="/watchlist" className="text-sm text-gray-600 hover:text-gray-900">Watchlist</Link>
          <Link href="/screener" className="text-sm text-gray-600 hover:text-gray-900">Screener</Link>
          <Link href="/alerts" className="text-sm text-gray-600 hover:text-gray-900">Alerts</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ben/alphaagent
git add dashboard/app/layout.tsx
git commit -m "feat: nav layout with links to all pages"
git push
```

---

### Task 18: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  python:
    name: Python tests
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: fastapi
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v

  typescript:
    name: TypeScript lint + typecheck
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: dashboard/package-lock.json
      - run: npm ci
      - run: npx tsc --noEmit
      - run: npx eslint . --ext .ts,.tsx --max-warnings 0
```

- [ ] **Step 2: Commit and verify CI passes**

```bash
cd /Users/ben/alphaagent
git add .github/
git commit -m "ci: GitHub Actions — Python pytest + TS typecheck on push"
git push
```

Open github.com/bsidebot/alphaagent/actions and confirm both jobs pass.

---

### Task 19: Daily Pipeline + Email Alerts

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `.github/workflows/daily_pipeline.yml`

- [ ] **Step 1: Create `scripts/run_pipeline.py`**

```python
"""
Daily pipeline: re-analyzes all watchlist tickers and fires alert emails.
Called by GitHub Actions daily_pipeline.yml.
"""
import os
import json
import time
import smtplib
import httpx
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ["NEXT_PUBLIC_APP_URL"]  # Vercel deployed URL
SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ["SMTP_PORT"])
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
DB_URL = os.environ["DATABASE_URL"]


def get_watchlist() -> list[str]:
    resp = httpx.get(f"{BASE_URL}/api/watchlist", timeout=10)
    return [item["ticker"] for item in resp.json()]


def trigger_analysis(ticker: str) -> dict:
    resp = httpx.post(f"{BASE_URL}/api/analyze/{ticker}", timeout=15)
    return resp.json()


def poll_until_complete(ticker: str, max_wait: int = 180) -> dict | None:
    for _ in range(max_wait // 5):
        time.sleep(5)
        result = httpx.get(f"{BASE_URL}/api/research/{ticker}", timeout=10).json()
        if result and result.get("status") == "complete":
            return result
        if result and result.get("status") == "error":
            print(f"Error analyzing {ticker}: {result.get('errorMsg')}")
            return None
    print(f"Timeout waiting for {ticker}")
    return None


def get_alert_rules() -> list[dict]:
    resp = httpx.get(f"{BASE_URL}/api/alerts", timeout=10)
    return [r for r in resp.json() if r["isActive"]]


def run_filters(filters: list[dict]) -> list[dict]:
    resp = httpx.post(
        f"{BASE_URL}/api/screener/run",
        json={"filters": filters},
        timeout=10,
    )
    return resp.json()


def send_email(to: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, to, msg.as_string())


def update_last_triggered(rule_id: str) -> None:
    httpx.patch(
        f"{BASE_URL}/api/alerts/{rule_id}",
        json={"lastTriggered": "now"},
        timeout=10,
    )


def main():
    print("=== AlphaAgent Daily Pipeline ===")

    watchlist = get_watchlist()
    print(f"Refreshing {len(watchlist)} tickers: {', '.join(watchlist)}")

    for ticker in watchlist:
        print(f"Analyzing {ticker}…")
        trigger_analysis(ticker)
        result = poll_until_complete(ticker)
        if result:
            print(f"  {ticker}: score={result.get('overallScore')} {result.get('recommendation')}")

    print("Checking alert rules…")
    rules = get_alert_rules()
    for rule in rules:
        matches = run_filters(rule["filters"])
        if matches:
            tickers = ", ".join(m["ticker"] for m in matches)
            body = f"""
            <h2>AlphaAgent Alert: {rule['name']}</h2>
            <p>The following tickers match your screener criteria:</p>
            <p><strong>{tickers}</strong></p>
            <p><a href="{BASE_URL}">View on AlphaAgent →</a></p>
            """
            send_email(rule["email"], f"AlphaAgent: {rule['name']} triggered", body)
            print(f"  Alert '{rule['name']}' → emailed {rule['email']} ({tickers})")
            update_last_triggered(rule["id"])

    print("Pipeline complete.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `.github/workflows/daily_pipeline.yml`**

```yaml
name: Daily Pipeline

on:
  schedule:
    - cron: "25 10 * * 1-5"  # 6:25am ET, weekdays
  workflow_dispatch:          # allow manual trigger from GitHub UI

jobs:
  pipeline:
    name: Refresh watchlist + check alerts
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install httpx python-dotenv
      - run: python scripts/run_pipeline.py
        env:
          NEXT_PUBLIC_APP_URL: ${{ secrets.NEXT_PUBLIC_APP_URL }}
          SMTP_HOST: smtp.gmail.com
          SMTP_PORT: "587"
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

- [ ] **Step 3: Add GitHub Actions secrets**

In github.com/bsidebot/alphaagent → Settings → Secrets → Actions → add:
- `NEXT_PUBLIC_APP_URL` — your Vercel deployment URL (after Task 20)
- `SMTP_USER` — Gmail address
- `SMTP_PASS` — Gmail App Password (generate at myaccount.google.com/apppasswords)
- `DATABASE_URL` — Neon connection string

- [ ] **Step 4: Commit**

```bash
cd /Users/ben/alphaagent
git add scripts/run_pipeline.py .github/workflows/daily_pipeline.yml
git commit -m "feat: daily pipeline — watchlist refresh + Nodemailer email alerts"
git push
```

---

### Task 20: Deploy to Vercel

**Files:** none (deployment via Vercel dashboard and CLI)

- [ ] **Step 1: Deploy the Next.js dashboard to Vercel**

```bash
cd /Users/ben/alphaagent/dashboard
npx vercel --prod
```

Follow prompts: link to a new Vercel project named `alphaagent`.

- [ ] **Step 2: Add environment variables in Vercel dashboard**

Go to vercel.com → alphaagent project → Settings → Environment Variables. Add:

```
DATABASE_URL          = <Neon connection string>
GEMINI_API_KEY        = <Google AI Studio key>
FASTAPI_URL           = https://alphaagent-fastapi.onrender.com
TRIGGER_SECRET_KEY    = <from Trigger.dev>
TRIGGER_PROJECT_REF   = <from Trigger.dev>
```

- [ ] **Step 3: Redeploy after adding env vars**

```bash
npx vercel --prod
```

- [ ] **Step 4: Run the Prisma migration on production**

```bash
cd /Users/ben/alphaagent/dashboard
DATABASE_URL="<neon-url>" npx prisma db push
```

Expected: `Your database is now in sync with your Prisma schema.`

- [ ] **Step 5: Smoke test the live app**

1. Open the Vercel URL
2. Search for `AAPL` — status indicator should appear and analysis should complete within ~60s
3. Click the research report — thesis and 4 agent cards should render
4. Add AAPL to watchlist — verify it appears on the watchlist page

- [ ] **Step 6: Add live URL to GitHub repo description**

```bash
gh repo edit bsidebot/alphaagent --description "Multi-agent stock research platform" --homepage "<vercel-url>"
```

- [ ] **Step 7: Final commit**

```bash
cd /Users/ben/alphaagent
git add .
git commit -m "chore: production deployment — Vercel + Render + Trigger.dev"
git push
```
