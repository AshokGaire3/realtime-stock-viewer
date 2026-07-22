"""ML price-prediction service.

Serving layer only: caches forecasts, computes display indicators, and shapes
the response. The forecast models themselves — linear-trend, random-walk,
drift, ml-momentum — live in `forecasters.py`, shared with the backtest
harness so what's evaluated is exactly what's served.

**On accuracy:** the reported figures come from the walk-forward backtest
(`scripts/backtest.py`), never from a model's own fit. `select_model()` picks
whichever candidate is *statistically* proven better than random-walk at this
horizon (`evaluation.py`); nothing beating it, it serves random-walk. That
selection updates automatically as more backtest/live data accumulates — no
code change needed for the served model to change.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import numpy as np
from sqlmodel import Session

from app.db import engine
from app.schemas import ChartData, Indicators, PredictionPoint, PredictionResult, ScoredPrediction, TodayShowcase
from app.services import providers
from app.services.cache import cache
from app.services.corpus import fetch_bars, load_series, store_bars
from app.services.evaluation import accuracy_for, select_model, todays_scored_points
from app.services.forecasters import MODELS, TRAIN_DAYS

PREDICT_TTL = 300
TODAY_TTL = 300

# yfinance strips timezone info but leaves the exchange-local wall-clock time
# in place, so bar timestamps read as naive US/Eastern. Regular-session close.
_MARKET_CLOSE_HOUR = 16
_MAX_TODAY_HORIZON = 8


def _compute_indicators(prices: np.ndarray) -> Indicators:
    def sma(n: int) -> float | None:
        return round(float(prices[-n:].mean()), 2) if len(prices) >= n else None

    rsi_14: float | None = None
    if len(prices) >= 15:
        deltas = np.diff(prices[-15:])
        gains = deltas[deltas > 0].sum()
        losses = -deltas[deltas < 0].sum()
        if losses == 0:
            rsi_14 = 100.0
        else:
            rs = (gains / 14) / (losses / 14)
            rsi_14 = round(100 - 100 / (1 + rs), 2)

    volatility: float | None = None
    if len(prices) >= 2:
        returns = np.diff(prices) / prices[:-1]
        volatility = round(float(returns.std() * np.sqrt(252)), 4)

    return Indicators(sma_20=sma(20), sma_50=sma(50), rsi_14=rsi_14, volatility=volatility)


def _next_trading_dates(start: datetime, n: int) -> list[datetime]:
    """The next `n` weekday dates after `start`, skipping Saturday/Sunday.

    Doesn't know about market holidays — a full trading calendar is more
    machinery than a display label needs — but it fixes the bulk of the
    mismatch: `horizon` is a count of trading days (the backtest and its
    accuracy figures are measured in trading-day steps), so stamping every
    step at `start + timedelta(days=i)` used to land forecast dates on
    weekends the market was never open.
    """
    dates: list[datetime] = []
    d = start
    while len(dates) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d)
    return dates


def _next_steps(start: datetime, n: int, interval: str) -> list[datetime]:
    """Timestamps for the next `n` forecast steps after `start`.

    Daily steps reuse `_next_trading_dates`. Intraday steps are simple fixed
    increments (e.g. +60m) that skip weekends only — a display label, not a
    full market-hours calendar. `/api/predict/today` bounds the horizon to
    the remaining trading day itself, so the imprecision here never actually
    surfaces a timestamp outside market hours in the showcase view.
    """
    if interval == "1d":
        return _next_trading_dates(start, n)
    step = timedelta(minutes=int(interval[:-1])) if interval.endswith("m") else timedelta(days=1)
    dates: list[datetime] = []
    d = start
    while len(dates) < n:
        d += step
        if d.weekday() < 5:
            dates.append(d)
    return dates


def _format_step(d: datetime, interval: str) -> str:
    return d.strftime("%Y-%m-%d") if interval == "1d" else d.isoformat(timespec="minutes")


async def _load_intraday(symbol: str, interval: str) -> tuple[np.ndarray, datetime]:
    """Real bars only, sourced the same way the live collector and backtest
    are — `corpus.fetch_bars` (yfinance) + `store_bars`, never the daily
    AV/Finnhub proxy, which has no intraday endpoint. Raises `CorpusError` if
    a fresh fetch fails and nothing is stored yet; never fabricates intraday
    data. Runs in a thread since `fetch_bars` is a blocking network call.
    """
    def _fetch_and_store() -> list:
        bars = fetch_bars(symbol, period="1d", interval=interval)
        with Session(engine) as session:
            store_bars(session, bars)
            return load_series(session, symbol, interval)

    series = await asyncio.to_thread(_fetch_and_store)
    prices = np.array([b.close for b in series], dtype=float)
    return prices, series[-1].ts


async def get_prediction(symbol: str, horizon: int = 7, interval: str = "1d") -> PredictionResult:
    cache_key = f"predict:{symbol.upper()}:{horizon}:{interval}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    if interval == "1d":
        # Raises UnknownSymbolError for unrecognised tickers rather than
        # forecasting invented prices; the router turns that into a 404.
        history, data_source = await providers.get_historical(symbol, TRAIN_DAYS)
        prices = np.array([h.price for h in history], dtype=float)
        last_ts = datetime.strptime(history[-1].date, "%Y-%m-%d")
    else:
        # Raises CorpusError (never fabricates) if intraday history can't be
        # fetched or stored yet; the router turns that into a 503.
        prices, last_ts = await _load_intraday(symbol, interval)
        data_source = "live"
    current_price = float(prices[-1])

    # Which model actually serves this forecast — statistically proven better
    # than random-walk on pooled backtest + live-scored evidence, or
    # random-walk itself if nothing has earned the win yet.
    with Session(engine) as session:
        model_name = select_model(session, horizon, interval=interval)
        # Same pooled basis `select_model` used, so the two never disagree
        # about whether the served model is actually winning.
        accuracy = accuracy_for(session, model_name, horizon, interval=interval, is_backtest=None)

    forecast, band = MODELS[model_name](prices, horizon)

    forecast_steps = _next_steps(last_ts, horizon, interval)
    points = [
        PredictionPoint(
            date=_format_step(forecast_steps[i], interval),
            predicted=round(float(forecast[i]), 2),
            lower=round(float(max(forecast[i] - band[i], 0.0)), 2),
            upper=round(float(forecast[i] + band[i]), 2),
        )
        for i in range(horizon)
    ]

    target = float(forecast[-1])
    pct = (target - current_price) / current_price if current_price else 0.0
    trend = "up" if pct > 0.005 else "down" if pct < -0.005 else "flat"

    result = PredictionResult(
        symbol=symbol.upper(),
        model=model_name,
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        current_price=round(current_price, 2),
        horizon_days=horizon,
        trend=trend,
        accuracy=accuracy,
        forecast=points,
        indicators=_compute_indicators(prices),
        data_source=data_source,
    )
    await cache.set(cache_key, result, PREDICT_TTL)
    return result


async def get_today_showcase(symbol: str, interval: str = "60m") -> TodayShowcase:
    """One trading day at hourly resolution: bars collected so far, the
    forecast for the remaining hours, and every prediction already labeled
    against reality today — the visible form of the same selection loop
    `get_prediction` uses.
    """
    cache_key = f"today:{symbol.upper()}:{interval}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    prices, last_ts = await _load_intraday(symbol, interval)

    with Session(engine) as session:
        series = load_series(session, symbol, interval)
    today = series[-1].ts.date()
    todays_bars = [b for b in series if b.ts.date() == today]

    close = last_ts.replace(hour=_MARKET_CLOSE_HOUR, minute=0, second=0, microsecond=0)
    remaining = int((close - last_ts).total_seconds() // 3600)
    horizon = min(max(remaining, 1), _MAX_TODAY_HORIZON)

    with Session(engine) as session:
        model_name = select_model(session, horizon, interval=interval)

    forecast, band = MODELS[model_name](prices, horizon)
    forecast_steps = _next_steps(last_ts, horizon, interval)
    forecast_points = [
        PredictionPoint(
            date=_format_step(forecast_steps[i], interval),
            predicted=round(float(forecast[i]), 2),
            lower=round(float(max(forecast[i] - band[i], 0.0)), 2),
            upper=round(float(forecast[i] + band[i]), 2),
        )
        for i in range(horizon)
    ]

    with Session(engine) as session:
        scored_rows = todays_scored_points(session, symbol, interval, model=model_name)

    result = TodayShowcase(
        symbol=symbol.upper(),
        interval=interval,
        trading_date=today.isoformat(),
        model=model_name,
        bars=[ChartData(date=b.ts.isoformat(timespec="minutes"), price=b.close, volume=b.volume) for b in todays_bars],
        forecast=forecast_points,
        scored=[ScoredPrediction(**row) for row in scored_rows],
        data_source="live",
    )
    await cache.set(cache_key, result, TODAY_TTL)
    return result
