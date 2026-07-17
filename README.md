# StockLab

**Live market data and ML price forecasts, with the API keys where they belong — on the server.**

StockLab is a stock and crypto dashboard that streams live quotes, charts historical prices,
and forecasts short-term price movement with a real (if modest) ML model. It exists mostly as
a study in doing the boring parts properly: no keys in the browser, upstream calls cached
against rate limits, and synthetic data that is always labelled as synthetic.

> ⚠️ Forecasts are educational estimates produced by a simple model. **Not financial advice.**

```
frontend/   React 18 + TypeScript + Vite + Tailwind + Recharts   → deploys to Vercel
backend/    FastAPI (Python) + Postgres                          → deploys to Render
```

## Why there's a backend

The original version called Alpha Vantage / Finnhub / CoinGecko straight from the browser,
which **published the API keys to anyone who opened devtools** and burned the free tier's rate
limit in a few refreshes. The backend fixes both: it holds the keys, proxies the requests,
and caches the responses. The frontend has no upstream credentials at all, and no client-side
fallback data — if a provider fails, the backend returns clearly-labelled synthetic data
rather than letting the UI invent prices that look live.

## What actually works today

| Endpoint | Does |
| --- | --- |
| `GET /api/stocks` | Quotes for a default watchlist |
| `GET /api/quote?symbol=` | Single quote |
| `GET /api/search?q=` | Symbol search |
| `GET /api/crypto` | Crypto prices (CoinGecko) |
| `GET /api/history?symbol=&days=` | Daily OHLC history, 1–365 days |
| `GET /api/predict?symbol=&horizon=` | Price forecast, 1–30 days, with confidence bands |
| `GET /api/health` | Health check (used by Render) |

Interactive API docs are at `/docs` on any running backend.

### Not built yet

The database schema in [`backend/app/models.py`](backend/app/models.py) defines tables for
**paper trading** (`Holding`, `Trade`), **lesson progress** (`LessonProgress`), and
**forecast accuracy evaluation** (`PriceBar`, `ForecastRun`, `ForecastPoint`). The paper-trading
and lesson tables are created at startup but **no endpoints read or write them yet** — the
schema is groundwork, not a working feature. The evaluation tables are written by the
backfill/backtest scripts and read by `/api/predict` — see
[Seeding the database](#seeding-the-database). Likewise the **AI tutor** and **indicator
explainers** are planned, not implemented; `ANTHROPIC_API_KEY` is currently unused.

The forecast model is a scikit-learn baseline. Prophet and LSTM are deliberately not
installed — they carry heavy build dependencies, and the baseline is what's honest to ship.

## Quick start

**Backend:**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # works without keys — you'll get labelled demo data
uvicorn app.main:app --reload --port 8000
```

**Frontend** (in a second terminal):

```bash
cd frontend
npm install
npm run dev                 # Vite proxies /api → http://localhost:8000
```

Open the printed Vite URL. It runs without any API keys; every value sourced from fallback
data is badged as demo in the UI.

## Seeding the database

`/api/predict` reports **measured** accuracy — looked up from scored backtests, never derived
from the fit. On an empty database there is nothing to look up, so `accuracy_for()` returns
`None` and the endpoint reports no accuracy at all. That's deliberate: inventing a confidence
number is the failure this replaced. Everything else works fine unseeded.

To populate it, run both scripts from `backend/` with the venv active:

```bash
# 1. Real daily bars via yfinance → the PriceBar corpus. Idempotent: re-running
#    only inserts dates not already stored.
python -m scripts.backfill --period 10y

# 2. Walk-forward backtest → scored ForecastPoints. Wipes prior backtest runs
#    and recomputes, so re-running is safe. Prints an accuracy table when done.
python -m scripts.backtest --horizon 30 --stride 5
```

Both default to the eight symbols in `POPULAR_STOCKS` (AAPL, GOOGL, MSFT, TSLA, AMZN, NVDA,
META, NFLX); pass `--symbols AAPL,MSFT` to narrow. The backtest fits models at many origins
across every symbol, so it takes a while.

To seed a **deployed** database, point `DATABASE_URL` at it first. Render's free tier has no
shell, so run this from your machine using the **External** Database URL (the Internal one
only resolves inside Render's network):

```bash
DATABASE_URL="postgres://...render.com/stocklab" python -m scripts.backfill --period 10y
DATABASE_URL="postgres://...render.com/stocklab" python -m scripts.backtest
```

The `postgres://` scheme Render hands out is normalised for SQLAlchemy automatically.

## Configuration (backend `.env`)

| Variable | Purpose |
| --- | --- |
| `ALPHA_VANTAGE_API_KEY` | Stock quotes & daily history. Omit for demo data. |
| `FINNHUB_API_KEY` | Backup stock quotes |
| `ANTHROPIC_API_KEY` | Reserved for the planned AI tutor; unused today |
| `ANTHROPIC_MODEL` | Optional; defaults to `claude-opus-4-8` |
| `DATABASE_URL` | Defaults to `sqlite:///./stocklab.db`; Postgres in production |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `CORS_ORIGIN_REGEX` | Optional regex, for Vercel preview URLs |

The frontend takes one variable, `VITE_API_BASE` — the backend's public origin. Leave it
unset in dev (Vite's proxy handles it). It must never hold an upstream provider key.

## Deploying

The two halves deploy separately: **Vercel** serves the static frontend, **Render** runs the
API and Postgres. GitHub Pages can't host this — it serves static files only, and there'd be
no API or database behind it.

### 1. Backend + database → Render

[`render.yaml`](render.yaml) is a blueprint that provisions both the web service and a free
Postgres instance, and wires `DATABASE_URL` between them automatically.

1. Render Dashboard → **New → Blueprint** → select this repo.
2. When prompted, fill in `ALPHA_VANTAGE_API_KEY`, `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`
   (blank is fine), and `CORS_ORIGINS`. These are marked `sync: false` so they're entered in
   the dashboard, never committed.
3. Deploy, then note the service URL: `https://stocklab-api.onrender.com`.

Tables are created on startup via `init_db()`, so there's no migration step. Postgres is used
rather than SQLite because Render's filesystem is ephemeral — a SQLite file would be silently
erased on every deploy.

> On Render's free tier the API sleeps after ~15 minutes idle, so the first request after a
> quiet spell takes ~30s to wake it. The free Postgres instance **expires after 90 days**.

### 2. Frontend → Vercel

1. Vercel → **Add New → Project** → import this repo.
2. Set **Root Directory** to `frontend`. ([`frontend/vercel.json`](frontend/vercel.json)
   supplies the build settings and the SPA rewrite.)
3. Add an environment variable: `VITE_API_BASE` = your Render URL from step 1.
4. Deploy.

> `VITE_API_BASE` is baked in at **build time**, not read at runtime. If it's missing the
> build still succeeds, but the app calls its own Vercel origin and every request 404s — so
> set it before deploying, and redeploy (not just restart) after changing it.

### 3. Close the CORS loop

Back on Render, set `CORS_ORIGINS` to your Vercel production URL (e.g.
`https://stocklab.vercel.app`). Preview deploys are already covered by the
`CORS_ORIGIN_REGEX` default in the blueprint. Without this the browser blocks every API call
while the backend looks perfectly healthy — it's the failure that wastes the most time here.

## License

MIT — use it for learning or your portfolio.

---

Built by [Ashok Gaire](https://github.com/AshokGaire3)
