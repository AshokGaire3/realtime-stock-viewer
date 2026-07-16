---
name: verify
description: Run and observe this repo's backend/frontend to verify a change works. Use when verifying any change to realtime-stock-viewer before committing.
---

# Verify realtime-stock-viewer

Run the thing and watch it. Tests and typecheck are not verification — see
[CLAUDE.md](../../../CLAUDE.md).

## Backend (FastAPI)

Boot on an **isolated port** (not 8000 — the user's dev server may hold it):

```bash
cd backend
(.venv/bin/uvicorn app.main:app --port 8137 > /tmp/uv.log 2>&1 &)
sleep 6 && cat /tmp/uv.log        # expect "Application startup complete"
curl -s localhost:8137/api/health # {"status":"ok"}
```

Kill it when done: `pkill -f "uvicorn app.main:app --port 8137"`.

The venv is at `backend/.venv` (Python 3.13) and is already populated — use
`.venv/bin/python`, don't create a new one. Pipe JSON through
`.venv/bin/python -m json.tool` or a small `-c` script; `jq` isn't guaranteed.

### Drive these

```bash
B=http://localhost:8137/api
curl -s "$B/stocks"                        # 8 stocks, mixed source tags
curl -s "$B/quote?symbol=MSFT"
curl -s "$B/history?symbol=AAPL&days=5"    # {symbol, source, points[5]}
curl -s "$B/search?q=apple"
curl -s "$B/crypto"
curl -s "$B/predict?symbol=AAPL&horizon=5" # forecast + indicators + data_source
```

Probes worth repeating: `horizon=0` / `horizon=31` → 422, missing `symbol` → 422,
`POST` → 405, unknown ticker (`ZZZZZ`) → **404, never a fabricated forecast**.

### Gotchas that will fool you

- **No `.env` exists by default**, so `alpha_vantage_api_key` falls back to the
  literal `"demo"`. Alpha Vantage's demo key **only serves MSFT** — every other
  symbol returns an `Information:` notice and no data. So `/api/stocks` legitimately
  returns MSFT as `source: "live"` and the other 7 as `source: "fallback"`. That is
  correct behaviour, not a bug.
- **CoinGecko is live and unkeyed**, so crypto paths hit the real network — they're
  the only reliably `"live"` data without a key. Slower (~1s) and can rate-limit.
- **Check `source` / `data_source` on every response.** Fallback data is synthetic
  and deterministic; a "working" chart may be entirely invented. Never report a
  forecast as validated when `data_source: "fallback"` — it's fitted on mock prices.
- **First `/predict` call is ~1.3s, second is ~7ms** (300s TTL cache). If a change
  looks like it had no effect, you may be reading a cached response — restart the
  server; the cache is in-process.

## Frontend (React + Vite)

```bash
cd frontend && npm run dev     # http://localhost:5173, proxies /api -> :8000
```

The vite proxy targets **port 8000**, so run the backend there (not 8137) when
driving the UI end-to-end, or set `BACKEND_URL`.

Screenshot the affected UI and inspect it, and check the browser console for errors
— required for any frontend change per CLAUDE.md.

**Current state:** `frontend/src/services/financialApi.ts` still calls Alpha Vantage /
Finnhub / CoinGecko **directly from the browser** with `VITE_*` keys — it is not yet
wired to the backend proxy. Until that's done, the UI does not exercise the backend
at all, and frontend types in `src/types/financial.ts` do **not** yet mirror
`backend/app/schemas.py` (missing `source`, `HistorySeries`, `data_source`).
