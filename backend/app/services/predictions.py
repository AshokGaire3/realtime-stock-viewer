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

from datetime import datetime, timedelta

import numpy as np
from sqlmodel import Session

from app.db import engine
from app.schemas import Indicators, PredictionPoint, PredictionResult
from app.services import providers
from app.services.cache import cache
from app.services.evaluation import accuracy_for, select_model
from app.services.forecasters import MODELS, TRAIN_DAYS

PREDICT_TTL = 300


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


async def get_prediction(symbol: str, horizon: int = 7) -> PredictionResult:
    cache_key = f"predict:{symbol.upper()}:{horizon}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    # Raises UnknownSymbolError for unrecognised tickers rather than forecasting
    # invented prices; the router turns that into a 404.
    history, data_source = await providers.get_historical(symbol, TRAIN_DAYS)
    prices = np.array([h.price for h in history], dtype=float)
    current_price = float(prices[-1])

    # Which model actually serves this forecast — statistically proven better
    # than random-walk, pooled across symbols, or random-walk itself if not.
    with Session(engine) as session:
        model_name = select_model(session, horizon)
    forecast, band = MODELS[model_name](prices, horizon)

    last_date = datetime.strptime(history[-1].date, "%Y-%m-%d")
    forecast_dates = _next_trading_dates(last_date, horizon)
    points = [
        PredictionPoint(
            date=forecast_dates[i].strftime("%Y-%m-%d"),
            predicted=round(float(forecast[i]), 2),
            lower=round(float(max(forecast[i] - band[i], 0.0)), 2),
            upper=round(float(forecast[i] + band[i]), 2),
        )
        for i in range(horizon)
    ]

    target = float(forecast[-1])
    pct = (target - current_price) / current_price if current_price else 0.0
    trend = "up" if pct > 0.005 else "down" if pct < -0.005 else "flat"

    # Accuracy is looked up from the backtest, never derived from the fit, and
    # pooled across symbols — the same basis `select_model` used to choose
    # `model_name`, so the two never disagree about whether it's winning.
    with Session(engine) as session:
        accuracy = accuracy_for(session, model_name, horizon)

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
