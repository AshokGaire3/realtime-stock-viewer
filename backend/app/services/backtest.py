"""Walk-forward backtest harness for the forecast models.

The whole point of this module is to answer "how far ahead can we forecast, and
how well" with a number that is not a lie. Two things make it not a lie:

1. **Point-in-time discipline.** A run as of bar `i` sees `bars[:i+1]` and
   nothing else. Letting a single future bar into the fit turns a useless model
   into a spectacular one, so `_slice` asserts the boundary rather than trusting
   the callers to slice correctly.
2. **Baselines.** An error number alone is decoration. Every model is scored
   against random-walk (tomorrow = today) and drift (today compounded by recent
   mean return) over the identical origins and horizons, so "good" has to mean
   "better than assuming nothing".

The production model is imported from `services.predictions`, not reimplemented
here — we evaluate what actually ships.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlmodel import Session, select

from app.models import ForecastPoint, ForecastRun, PriceBar
from app.services.corpus import load_series
from app.services.predictions import TRAIN_DAYS, _fit_and_forecast

# Models under test. Each takes the training closes and a horizon, and returns
# (forecast, band_halfwidth) over steps 1..horizon.
Forecaster = "Callable[[np.ndarray, int], tuple[np.ndarray, np.ndarray]]"


def _linear_trend(prices: np.ndarray, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """The shipped model (app/services/predictions.py)."""
    forecast, band, _r2 = _fit_and_forecast(prices, horizon)
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


MODELS = {
    "linear-trend": _linear_trend,
    "random-walk": _random_walk,
    "drift": _drift,
}


@dataclass
class Origin:
    """One point in time to forecast from, with its train/test split."""

    index: int
    train: np.ndarray  # closes the model may see
    actuals: np.ndarray  # closes for steps 1..h (may be shorter near the end)
    as_of: PriceBar
    targets: list[PriceBar]


def _slice(series: list[PriceBar], i: int, horizon: int, train_days: int) -> Origin:
    """Build the train/test split at bar `i`, enforcing the leak boundary."""
    train_bars = series[i + 1 - train_days : i + 1]
    target_bars = series[i + 1 : i + 1 + horizon]

    # The invariant this whole harness rests on: nothing the model sees may be
    # dated at or after the first thing it is asked to predict.
    if target_bars:
        assert train_bars[-1].date < target_bars[0].date, (
            f"lookahead leak at {series[i].symbol} bar {i}: "
            f"train ends {train_bars[-1].date}, target starts {target_bars[0].date}"
        )

    return Origin(
        index=i,
        train=np.array([b.close for b in train_bars], dtype=float),
        actuals=np.array([b.close for b in target_bars], dtype=float),
        as_of=series[i],
        targets=target_bars,
    )


def iter_origins(
    series: list[PriceBar], horizon: int, train_days: int, stride: int
) -> list[Origin]:
    """Every origin with a full training window and at least one real target."""
    first = train_days - 1
    last = len(series) - 2  # need >=1 future bar to score against
    return [_slice(series, i, horizon, train_days) for i in range(first, last + 1, stride)]


def _score(
    origin: Origin, forecast: np.ndarray, band: np.ndarray, run_id: int
) -> list[ForecastPoint]:
    anchor = float(origin.train[-1])
    points: list[ForecastPoint] = []
    for step in range(1, len(forecast) + 1):
        idx = step - 1
        pred = float(forecast[idx])
        half = float(band[idx])
        lower, upper = max(pred - half, 0.0), pred + half

        point = ForecastPoint(
            run_id=run_id,
            step=step,
            target_date=(
                origin.targets[idx].date
                if idx < len(origin.targets)
                # No bar to score against (end of corpus); date is unknown, so
                # reuse as_of and leave the actual null.
                else origin.as_of.date
            ),
            predicted=round(pred, 4),
            lower=round(lower, 4),
            upper=round(upper, 4),
        )
        if idx < len(origin.actuals):
            actual = float(origin.actuals[idx])
            point.actual = round(actual, 4)
            point.abs_error = round(abs(pred - actual), 4)
            point.pct_error = round(abs(pred - actual) / actual, 6) if actual else None
            point.in_band = bool(lower <= actual <= upper)
            # Sign of the predicted move vs the sign of the real move. Flat
            # predictions (random-walk) never "hit" — correct: no call, no credit.
            point.direction_hit = bool(np.sign(pred - anchor) == np.sign(actual - anchor))
        points.append(point)
    return points


def run_backtest(
    session: Session,
    symbols: list[str],
    horizon: int = 30,
    train_days: int = TRAIN_DAYS,
    stride: int = 5,
    models: list[str] | None = None,
) -> dict[str, int]:
    """Fit/predict/score every model at every origin. Returns per-model run counts."""
    chosen = models or list(MODELS)
    counts = {m: 0 for m in chosen}

    for symbol in symbols:
        series = load_series(session, symbol)
        if len(series) < train_days + 2:
            raise ValueError(
                f"{symbol}: only {len(series)} bars stored, need at least {train_days + 2}. "
                "Backfill the corpus first."
            )
        origins = iter_origins(series, horizon, train_days, stride)

        for name in chosen:
            forecaster = MODELS[name]
            for origin in origins:
                forecast, band = forecaster(origin.train, horizon)
                run = ForecastRun(
                    model=name,
                    symbol=symbol.upper(),
                    as_of_date=origin.as_of.date,
                    horizon_days=horizon,
                    train_days=len(origin.train),
                    anchor_price=float(origin.train[-1]),
                    is_backtest=True,
                )
                session.add(run)
                session.flush()  # assign run.id without a full commit per run
                session.add_all(_score(origin, forecast, band, run.id))
                counts[name] += 1
            session.commit()

    return counts


def clear_backtests(session: Session) -> None:
    """Drop prior backtest runs so a re-run doesn't double-count."""
    runs = session.exec(select(ForecastRun).where(ForecastRun.is_backtest == True)).all()  # noqa: E712
    ids = [r.id for r in runs]
    for point in session.exec(select(ForecastPoint).where(ForecastPoint.run_id.in_(ids))).all():
        session.delete(point)
    for run in runs:
        session.delete(run)
    session.commit()
