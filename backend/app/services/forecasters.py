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
# endpoint fit on comparable windows. 300 comfortably covers a ~252-trading-day
# (one year) lookback feature for ml-momentum with margin left for training
# examples; bumped from 120, which could never see a year back regardless of
# how much real history existed upstream.
TRAIN_DAYS = 300

# Default training-window bar counts by interval, shared by the live
# serving path, the live collector, and the backtest CLI so all three fit on
# the identical window — otherwise the accuracy the backtest measures
# describes a different fit than the one actually served. Daily reuses the
# shipped model's own TRAIN_DAYS. 60m is trimmed to 150 (~21 trading days)
# rather than the full 60-day/~420-bar intraday corpus, leaving enough
# origins in that corpus for a walk-forward backtest at a week-long (49-step)
# horizon. Anything else intraday falls back to ~5 trading days of 5-min bars.
DEFAULT_TRAIN_BARS = {"1d": TRAIN_DAYS, "60m": 150}
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
    """9 features describing the tail of `prices` across short, medium, and
    long lookbacks: returns at ~day/week/month/quarter/year bar-counts,
    RSI-14, volatility at two horizons, and the SMA20/SMA50 ratio. `prices`
    is truncated to "history as of this point" by the caller — this only
    ever looks backward.

    "Month"/"quarter"/"year" are bar counts (21/60/252), not literal
    calendar spans — on the daily model they line up with trading-day
    convention; on the hourly model (60-day yfinance intraday cap) 252 bars
    is ~36 trading days, not a year. `log_ret`/vol already degrade to `0.0`
    when there isn't enough history yet, so no extra guard is needed here —
    early training examples in a window just see a flat 0.0 for whichever
    lookback isn't available yet.
    """
    log_p = np.log(prices)

    def log_ret(n: int) -> float:
        return float(log_p[-1] - log_p[-1 - n]) if len(log_p) > n else 0.0

    def vol(n: int) -> float:
        return float(np.diff(log_p[-n - 1 :]).std() * np.sqrt(252)) if len(prices) > n else 0.0

    deltas = np.diff(prices[-15:])
    gains = deltas[deltas > 0].sum()
    losses = -deltas[deltas < 0].sum()
    if losses == 0:
        rsi_14 = 100.0
    else:
        rs = (gains / 14) / (losses / 14)
        rsi_14 = 100 - 100 / (1 + rs)

    sma_20 = float(prices[-20:].mean())
    sma_50 = float(prices[-50:].mean())

    return np.array(
        [
            log_ret(1),  # ~day
            log_ret(5),  # ~week
            log_ret(21),  # ~month
            log_ret(60),  # ~quarter
            log_ret(252),  # ~year (bar-count; see docstring)
            rsi_14,
            vol(20),
            vol(60),
            sma_20 / sma_50,
        ],
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
