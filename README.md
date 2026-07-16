# Realtime Stock Viewer — AI Prediction & Learning Platform

An interactive platform to **watch live markets**, **predict** price movement with real ML,
and **learn** about investing through an AI tutor, interactive indicator explainers, guided
lessons, and a paper-trading simulator.

This is a monorepo:

```
frontend/   React 18 + TypeScript + Vite + Tailwind + Recharts  (the UI)
backend/    FastAPI (Python)                                     (data proxy, ML, AI tutor, DB)
```

## Why a backend?

The original app called Alpha Vantage / Finnhub / CoinGecko directly from the browser, which
**exposed the API keys publicly** and hit free-tier **rate limits**. The backend now:

- Holds all upstream API keys server-side and **proxies** market data (`/api/quote`, `/api/history`).
- **Caches** responses to stay under rate limits.
- Runs **ML price predictions** (Prophet / scikit-learn, optional LSTM) — `/api/predict`.
- Hosts an **AI tutor + indicator explainers** via the Claude API — `/api/tutor`, `/api/explain`.
- Persists **paper trading** and **lesson progress** in SQLite.

> ⚠️ Predictions are educational estimates, **not financial advice**.

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in ALPHA_VANTAGE_API_KEY, FINNHUB_API_KEY, ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                 # Vite dev server proxies /api → http://localhost:8000
```

Open the printed Vite URL. The frontend talks only to the backend; no API keys ship to the browser.

## Environment variables (backend `.env`)

| Variable                  | Purpose                                            |
| ------------------------- | -------------------------------------------------- |
| `ALPHA_VANTAGE_API_KEY`   | Stock quotes & daily history                        |
| `FINNHUB_API_KEY`         | Backup stock quotes                                 |
| `ANTHROPIC_API_KEY`       | Claude API for the AI tutor & explainers            |
| `ANTHROPIC_MODEL`         | Optional; defaults to `claude-opus-4-8`             |
| `DATABASE_URL`            | Optional; defaults to `sqlite:///./stockviewer.db`  |
| `CORS_ORIGINS`            | Optional; comma-separated allowed origins           |
