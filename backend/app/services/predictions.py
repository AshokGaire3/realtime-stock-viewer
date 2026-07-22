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
from app.services.cache import cache
from app.services.corpus import fetch_bars, load_series, store_bars
from app.services.evaluation import accuracy_for, select_model, todays_scored_points
from app.services.forecasters import DEFAULT_TRAIN_BARS, FALLBACK_INTRADAY_TRAIN_BARS, MODELS

PREDICT_TTL = 300
TODAY_TTL = 300

# yfinance strips timezone info but leaves the exchange-local wall-clock time
# in place, so bar timestamps read as naive US/Eastern.
_MARKET_OPEN = (9, 30)
_MARKET_CLOSE = (15, 30)  # last hourly bar of the trading day
_BARS_PER_DAY = 7  # 09:30, 10:30, ..., 15:30
_MAX_WINDOW_DAYS = 7


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


def _next_market_hour(d: datetime) -> datetime:
    """The next hourly bar timestamp after `d`, one step of a trading-hours
    calendar: advances an hour within the session, then rolls to the next
    weekday's 09:30 open once a day's 15:30 bar is passed. Only correct for
    hourly (`60m`) bars, matching the 7-bars/day alignment the corpus already
    stores (09:30, 10:30, ..., 15:30).
    """
    d = d + timedelta(hours=1)
    close_today = d.replace(hour=_MARKET_CLOSE[0], minute=_MARKET_CLOSE[1], second=0, microsecond=0)
    if d > close_today or d.weekday() >= 5:
        d = d.replace(hour=_MARKET_OPEN[0], minute=_MARKET_OPEN[1], second=0, microsecond=0)
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return d


def _next_steps(start: datetime, n: int, interval: str) -> list[datetime]:
    """Timestamps for the next `n` forecast steps after `start`. Daily steps
    reuse `_next_trading_dates`; hourly steps use the trading-hours calendar
    above so a multi-day window never lands a forecast at 11pm or on a
    weekend.
    """
    if interval == "1d":
        return _next_trading_dates(start, n)
    dates: list[datetime] = []
    d = start
    while len(dates) < n:
        d = _next_market_hour(d)
        dates.append(d)
    return dates


def _format_step(d: datetime, interval: str) -> str:
    return d.strftime("%Y-%m-%d") if interval == "1d" else d.isoformat(timespec="minutes")


def _train_bars(interval: str) -> int:
    """The training window this interval is actually backtested at
    (`forecasters.DEFAULT_TRAIN_BARS`) — serving must fit on the identical
    window the reported accuracy was measured on, not on however much
    history happens to be stored.
    """
    return DEFAULT_TRAIN_BARS.get(interval, FALLBACK_INTRADAY_TRAIN_BARS)


async def _load_from_corpus(symbol: str, interval: str, period: str) -> list:
    """Real bars only, sourced the same way the backtest and live collector
    are — `corpus.fetch_bars` (yfinance) + `store_bars` — for both daily and
    intraday prediction. Used instead of the Alpha Vantage/Finnhub proxy in
    `providers.py`, whose daily endpoint defaults to its "compact" mode (last
    100 points) and has no intraday endpoint at all; yfinance has neither
    limit at the depths this app needs. Raises `CorpusError` if a fresh fetch
    fails and nothing is stored yet; never fabricates data. Runs in a thread
    since `fetch_bars` is a blocking network call. Returns the full stored
    `PriceBar` series (not just closes) so callers can render a history line
    from the identical source the forecast itself is fit on — mixing this
    with `/api/history`'s AV/Finnhub-backed series risks two different
    "current prices" on the same chart if one proxy is rate-limited.
    """
    def _fetch_and_store() -> list:
        bars = fetch_bars(symbol, period=period, interval=interval)
        with Session(engine) as session:
            store_bars(session, bars)
            return load_series(session, symbol, interval)

    return await asyncio.to_thread(_fetch_and_store)


async def get_prediction(symbol: str, horizon: int = 7, interval: str = "1d") -> PredictionResult:
    cache_key = f"predict:{symbol.upper()}:{horizon}:{interval}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    # Raises CorpusError (never fabricates) if history can't be fetched or
    # stored yet; the router turns that into a 503. "2y" comfortably covers
    # TRAIN_DAYS (300) for daily; intraday uses whatever's already collected.
    period = "2y" if interval == "1d" else "1d"
    series = await _load_from_corpus(symbol, interval, period)
    train_bars = _train_bars(interval)
    prices = np.array([b.close for b in series], dtype=float)[-train_bars:]
    last_ts = series[-1].ts
    data_source = "live"
    current_price = float(prices[-1])

    # Same corpus the forecast is fit on, so the chart's history line and the
    # forecast line never disagree about what "now" is worth.
    history_bars = series[-min(train_bars, 30) :]

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
        history=[
            ChartData(date=_format_step(b.ts, interval), price=round(b.close, 2), volume=b.volume)
            for b in history_bars
        ],
        forecast=points,
        indicators=_compute_indicators(prices),
        data_source=data_source,
    )
    await cache.set(cache_key, result, PREDICT_TTL)
    return result


async def get_today_showcase(symbol: str, interval: str = "60m", days: int = 1) -> TodayShowcase:
    """Today's bars so far, an hourly forecast spanning `days` trading days
    (1-7, most-detailed at 1), and every prediction already labeled against
    reality today — the visible form of the same selection loop
    `get_prediction` uses.
    """
    days = min(max(days, 1), _MAX_WINDOW_DAYS)
    cache_key = f"today:{symbol.upper()}:{interval}:{days}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    series = await _load_from_corpus(symbol, interval, period="1d")
    prices = np.array([b.close for b in series], dtype=float)[-_train_bars(interval) :]
    last_ts = series[-1].ts
    today = series[-1].ts.date()
    todays_bars = [b for b in series if b.ts.date() == today]

    # Bars already printed today, by wall-clock position in the session.
    open_today = last_ts.replace(hour=_MARKET_OPEN[0], minute=_MARKET_OPEN[1], second=0, microsecond=0)
    bars_so_far = int((last_ts - open_today).total_seconds() // 3600) + 1
    remaining_today = max(_BARS_PER_DAY - bars_so_far, 0)
    # If today's session is already over, "1 day" means the next full trading
    # day rather than zero forecast points.
    horizon = (
        remaining_today + (days - 1) * _BARS_PER_DAY
        if remaining_today > 0
        else days * _BARS_PER_DAY
    )

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
