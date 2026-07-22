"""Forecast model registry — every candidate the backtest and the live endpoint
can serve, behind one interface: `(prices: np.ndarray, horizon: int) -> (forecast,
band_halfwidth)`.

Kept separate from both `predictions.py` (serving: caching, indicators, response
shaping) and `backtest.py` (evaluation harness) so neither has to import the
other to reach the model implementations — `evaluation.select_model()` decides
*which* entry in `MODELS` gets served, using accuracy measured here against the
identical models the backtest already scored.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

# Train on this many days of history; shared so the backtest and the live
# endpoint fit on comparable windows.
TRAIN_DAYS = 120

# Default training-window bar counts by interval, shared by the live collector
# and the backtest CLI so both fit on comparable windows. Daily reuses the
# shipped model's own TRAIN_DAYS; anything intraday falls back to ~5 trading
# days' worth of 60-minute bars (78 bars/day at 5m, ~7 at 60m — 390 covers a
# 5m corpus's yfinance lookback cap and is a reasonable default for 60m too).
DEFAULT_TRAIN_BARS = {"1d": TRAIN_DAYS}
FALLBACK_INTRADAY_TRAIN_BARS = 390

BandFn = Callable[[np.ndarray, np.ndarray, int], np.ndarray]
Forecaster = Callable[[np.ndarray, int], "tuple[np.ndarray, np.ndarray]"]


def _static_vol_band(y: np.ndarray, forecast: np.ndarray, horizon: int) -> np.ndarray:
    """Band from the std of daily log returns — the one-step innovation. Using
    the residuals around the trend line instead conflates trend misfit with
    step-to-step uncertainty, giving a "95%" band that measured ~99% coverage.
    """
    sigma = float(np.diff(y).std())
    steps = np.arange(1, horizon + 1)
    return forecast * (np.exp(1.96 * sigma * np.sqrt(steps)) - 1)


def _fit_and_forecast(
    prices: np.ndarray, horizon: int, band_fn: BandFn = _static_vol_band
) -> tuple[np.ndarray, np.ndarray]:
    """Fit log-linear trend; return (forecast, band_halfwidth).

    `band_fn` is swappable so the backtest harness can score alternative band
    strategies (e.g. an EWMA-weighted volatility estimate) against the same
    trend fit, without duplicating this function.
    """
    n = len(prices)
    x = np.arange(n).reshape(-1, 1)
    y = np.log(prices)

    model = LinearRegression().fit(x, y)
    fitted = model.predict(x)

    future_x = np.arange(n, n + horizon).reshape(-1, 1)
    log_forecast = model.predict(future_x)

    # Anchor to the last close. The fitted line does not pass through the final
    # observation, and the gap is big: measured at ~5.8% on AAPL (worst 32%)
    # against a typical 1-day move of 1.26%. Unanchored, the forecast opens day
    # 1 that far from a price we already know, and every later step inherits the
    # offset — it cost ~333% MAE at 1 day in backtest.
    log_forecast = log_forecast + (y[-1] - fitted[-1])
    forecast = np.exp(log_forecast)

    band = band_fn(y, forecast, horizon)
    return forecast, band


def _random_walk(prices: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Tomorrow = today. The honest null hypothesis for a price series."""
    last = float(prices[-1])
    forecast = np.full(horizon, last)
    # Band from historical daily vol, widening with sqrt(steps) — same shape of
    # assumption the production band makes, so coverage is comparable.
    sigma = float(np.diff(np.log(prices)).std())
    steps = np.arange(1, horizon + 1)
    band = forecast * (np.exp(1.96 * sigma * np.sqrt(steps)) - 1)
    return forecast, band


def _drift(prices: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Today compounded forward at the mean daily log return."""
    log_p = np.log(prices)
    mu = float(np.diff(log_p).mean())
    sigma = float(np.diff(log_p).std())
    steps = np.arange(1, horizon + 1)
    forecast = np.exp(log_p[-1] + mu * steps)
    band = forecast * (np.exp(1.96 * sigma * np.sqrt(steps)) - 1)
    return forecast, band


# --- ml-momentum ---
#
# A RandomForestRegressor over momentum/mean-reversion features, trained
# walk-forward from the same window it forecasts from — every training example
# below is built only from data that precedes its own target, so fitting here
# carries no more lookahead risk than the backtest harness that later scores it.

_MOMENTUM_LOOKBACK = 50  # longest feature window (SMA-50); caps how far back a training example can start
_MIN_TRAIN_EXAMPLES = 10


def _momentum_features(prices: np.ndarray) -> np.ndarray:
    """7 features describing the tail of `prices`: recent returns, RSI-14,
    annualized volatility, and the SMA20/SMA50 ratio. `prices` is truncated to
    "history as of this point" by the caller — this only ever looks backward.
    """
    log_p = np.log(prices)

    def log_ret(n: int) -> float:
        return float(log_p[-1] - log_p[-1 - n]) if len(log_p) > n else 0.0

    deltas = np.diff(prices[-15:])
    gains = deltas[deltas > 0].sum()
    losses = -deltas[deltas < 0].sum()
    if losses == 0:
        rsi_14 = 100.0
    else:
        rs = (gains / 14) / (losses / 14)
        rsi_14 = 100 - 100 / (1 + rs)

    vol_20 = float(np.diff(log_p[-21:]).std() * np.sqrt(252)) if len(prices) >= 21 else 0.0
    sma_20 = float(prices[-20:].mean())
    sma_50 = float(prices[-50:].mean())

    return np.array(
        [log_ret(1), log_ret(5), log_ret(10), log_ret(20), rsi_14, vol_20, sma_20 / sma_50],
        dtype=float,
    )


def _ml_momentum(prices: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Predict the terminal h-step log-return from momentum features, learned
    from every valid (features, realized return) pair inside the training
    window itself — not from any data outside `prices`.

    This is a single terminal-return prediction, not 30 independent per-step
    fits: intermediate steps are shaped by scaling that terminal return
    linearly (in log-space) by `step / horizon`, the same simplification
    `_drift` makes. Predicting each step independently would need `horizon`x
    the model fits per origin for a marginal gain over this shape.
    """
    n = len(prices)
    first_feature_idx = _MOMENTUM_LOOKBACK - 1  # need 50 bars of history behind it
    last_origin_idx = n - 1 - horizon  # need `horizon` bars ahead to realize the target

    X, y = [], []
    for j in range(first_feature_idx, last_origin_idx + 1):
        X.append(_momentum_features(prices[: j + 1]))
        y.append(np.log(prices[j + horizon] / prices[j]))

    if len(X) < _MIN_TRAIN_EXAMPLES:
        raise ValueError(
            f"ml-momentum needs >={_MIN_TRAIN_EXAMPLES} training examples, got {len(X)} "
            f"(prices={n}, horizon={horizon}). Needs more history or a shorter horizon."
        )

    model = RandomForestRegressor(n_estimators=50, max_depth=4, random_state=0)
    model.fit(np.array(X), np.array(y))

    terminal_return = float(model.predict(_momentum_features(prices).reshape(1, -1))[0])
    steps = np.arange(1, horizon + 1)
    forecast = prices[-1] * np.exp(terminal_return * steps / horizon)

    sigma = float(np.diff(np.log(prices)).std())
    band = forecast * (np.exp(1.96 * sigma * np.sqrt(steps)) - 1)
    return forecast, band


MODELS: dict[str, Forecaster] = {
    "linear-trend": _fit_and_forecast,
    "random-walk": _random_walk,
    "drift": _drift,
    "ml-momentum": _ml_momentum,
}
