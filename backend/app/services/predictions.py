"""ML price-prediction service (Phase 2 baseline).

A deliberately simple, explainable scikit-learn baseline: we fit a linear
regression on *log* prices against a time index (so the forecast compounds
rather than going negative), then project forward. The confidence band widens
with the square root of the horizon to reflect growing uncertainty, and the
reported `confidence` blends the in-sample fit (R^2) with how wide that band
gets relative to price.

Heavier models (Prophet, LSTM) are slotted for a later phase behind the same
interface; the router only ever sees `PredictionResult`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
from sklearn.linear_model import LinearRegression

from app.schemas import Indicators, PredictionPoint, PredictionResult
from app.services import providers
from app.services.cache import cache

# Train on this many days of history and cache each forecast briefly so repeated
# loads of the same symbol don't refit.
TRAIN_DAYS = 120
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


def _fit_and_forecast(prices: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray, float]:
    """Fit log-linear trend; return (forecast, band_halfwidth, r2)."""
    n = len(prices)
    x = np.arange(n).reshape(-1, 1)
    y = np.log(prices)

    model = LinearRegression().fit(x, y)
    r2 = float(model.score(x, y))

    # Residual std in log space drives the confidence band.
    resid_std = float((y - model.predict(x)).std())

    future_x = np.arange(n, n + horizon).reshape(-1, 1)
    log_forecast = model.predict(future_x)
    forecast = np.exp(log_forecast)

    # Band widens with sqrt(steps-ahead); ~1.96 sigma ≈ 95% under log-normality.
    steps = np.arange(1, horizon + 1)
    band = forecast * (np.exp(1.96 * resid_std * np.sqrt(steps)) - 1)
    return forecast, band, r2


async def get_prediction(symbol: str, horizon: int = 7) -> PredictionResult:
    cache_key = f"predict:{symbol.upper()}:{horizon}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    # Raises UnknownSymbolError for unrecognised tickers rather than forecasting
    # invented prices; the router turns that into a 404.
    history, data_source = await providers.get_historical(symbol, TRAIN_DAYS)
    prices = np.array([h.price for h in history], dtype=float)
    current_price = float(prices[-1])

    forecast, band, r2 = _fit_and_forecast(prices, horizon)

    last_date = datetime.strptime(history[-1].date, "%Y-%m-%d")
    points = [
        PredictionPoint(
            date=(last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d"),
            predicted=round(float(forecast[i]), 2),
            lower=round(float(max(forecast[i] - band[i], 0.0)), 2),
            upper=round(float(forecast[i] + band[i]), 2),
        )
        for i in range(horizon)
    ]

    target = float(forecast[-1])
    pct = (target - current_price) / current_price if current_price else 0.0
    trend = "up" if pct > 0.005 else "down" if pct < -0.005 else "flat"

    # Confidence: good fit and a tight final band → high; poor fit / wide band → low.
    rel_band = float(band[-1] / target) if target else 1.0
    confidence = round(max(0.0, min(1.0, max(r2, 0.0) * (1 - min(rel_band, 1.0)))), 3)

    result = PredictionResult(
        symbol=symbol.upper(),
        model="linear-trend",
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        current_price=round(current_price, 2),
        horizon_days=horizon,
        trend=trend,
        confidence=confidence,
        forecast=points,
        indicators=_compute_indicators(prices),
        data_source=data_source,
    )
    await cache.set(cache_key, result, PREDICT_TTL)
    return result
