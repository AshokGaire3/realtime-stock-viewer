"""Walk-forward backtest harness for the forecast models.

The whole point of this module is to answer "how far ahead can we forecast, and
how well" with a number that is not a lie. Two things make it not a lie:

1. **Point-in-time discipline.** A run as of bar `i` sees `bars[:i+1]` and
   nothing else. Letting a single future bar into the fit turns a useless model
   into a spectacular one, so scoring (`score_pending`) is structurally unable
   to match a step to anything but a later bar — see that function's docstring.
2. **Baselines.** An error number alone is decoration. Every model is scored
   against random-walk (tomorrow = today) and drift (today compounded by recent
   mean return) over the identical origins and horizons, so "good" has to mean
   "better than assuming nothing".

Models under test come from `services.forecasters.MODELS` — the same registry
`services.predictions` serves from — so we evaluate exactly what can ship.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlmodel import Session, select

from app.models import ForecastPoint, ForecastRun, PriceBar
from app.services.corpus import load_series
from app.services.forecasters import MODELS, TRAIN_DAYS


@dataclass
class Origin:
    """One point in time to forecast from, with its train window."""

    index: int
    train: np.ndarray  # closes the model may see
    as_of: PriceBar


def _slice(series: list[PriceBar], i: int, train_days: int) -> Origin:
    """Build the training window ending at bar `i`."""
    train_bars = series[i + 1 - train_days : i + 1]
    return Origin(index=i, train=np.array([b.close for b in train_bars], dtype=float), as_of=series[i])


def iter_origins(series: list[PriceBar], train_days: int, stride: int) -> list[Origin]:
    """Every origin with a full training window and at least one future bar to score."""
    first = train_days - 1
    last = len(series) - 2  # need >=1 future bar to score against
    return [_slice(series, i, train_days) for i in range(first, last + 1, stride)]


def score_pending(session: Session, symbol: str, interval: str = "1d") -> int:
    """Fill in actual/error/coverage for every unscored point of this symbol+interval.

    Scores by ordinal step, not by a precomputed calendar date: step N is
    matched to the Nth real bar after its run's `as_of_ts`, whichever bar that
    turns out to be. This is what lets one scoring path serve both the
    backtest (all targets already exist) and the live collector (targets
    arrive one bar at a time) — and it needs no market calendar, since
    weekends and holidays are simply absent from the bar sequence.

    No separate lookahead guard is needed here (the old harness had one as a
    runtime `assert`, which silently vanishes under `python -O`): `series` is
    ordered ascending by `ts` and `target_idx = origin_idx + step` with
    `step >= 1`, so the target bar is structurally always later than the
    origin bar — there is no code path that can construct a leak.
    """
    series = load_series(session, symbol, interval)
    ts_index = {bar.ts: i for i, bar in enumerate(series)}

    run_ids = session.exec(
        select(ForecastRun.id)
        .where(ForecastRun.symbol == symbol.upper())
        .where(ForecastRun.interval == interval)
    ).all()
    if not run_ids:
        return 0

    pending = session.exec(
        select(ForecastPoint, ForecastRun.as_of_ts, ForecastRun.anchor_price)
        .join(ForecastRun, ForecastPoint.run_id == ForecastRun.id)
        .where(ForecastPoint.run_id.in_(run_ids))
        .where(ForecastPoint.actual == None)  # noqa: E711
    ).all()

    scored = 0
    for point, as_of_ts, anchor in pending:
        origin_idx = ts_index.get(as_of_ts)
        if origin_idx is None:
            continue  # as_of bar not (yet) in this series — shouldn't happen, skip defensively
        target_idx = origin_idx + point.step
        if target_idx >= len(series):
            continue  # target bar hasn't happened yet

        bar = series[target_idx]
        pred, actual = point.predicted, float(bar.close)
        point.target_ts = bar.ts
        point.actual = round(actual, 4)
        point.abs_error = round(abs(pred - actual), 4)
        point.pct_error = round(abs(pred - actual) / actual, 6) if actual else None
        point.in_band = bool(point.lower <= actual <= point.upper)
        # Sign of the predicted move vs the sign of the real move. Flat
        # predictions (random-walk) never "hit" — correct: no call, no credit.
        # `pred` is stored rounded to 4dp but `anchor` is not, so a flat
        # forecast (pred == anchor before rounding) can come out as a tiny
        # nonzero residual with an essentially random sign. Round anchor to
        # the same precision before diffing so a genuinely flat call reads as
        # sign 0, not noise.
        point.direction_hit = bool(np.sign(pred - round(anchor, 4)) == np.sign(actual - anchor))
        session.add(point)
        scored += 1

    session.commit()
    return scored


def run_backtest(
    session: Session,
    symbols: list[str],
    horizon: int = 30,
    train_days: int = TRAIN_DAYS,
    stride: int = 5,
    models: list[str] | None = None,
    interval: str = "1d",
) -> dict[str, int]:
    """Fit/predict every model at every origin, then score against the corpus.

    Returns per-model run counts.
    """
    chosen = models or list(MODELS)
    counts = {m: 0 for m in chosen}

    for symbol in symbols:
        series = load_series(session, symbol, interval)
        if len(series) < train_days + 2:
            raise ValueError(
                f"{symbol}: only {len(series)} bars stored, need at least {train_days + 2}. "
                "Backfill the corpus first."
            )
        origins = iter_origins(series, train_days, stride)

        for name in chosen:
            forecaster = MODELS[name]
            for origin in origins:
                forecast, band = forecaster(origin.train, horizon)
                run = ForecastRun(
                    model=name,
                    symbol=symbol.upper(),
                    interval=interval,
                    as_of_ts=origin.as_of.ts,
                    horizon=horizon,
                    train_days=len(origin.train),
                    anchor_price=float(origin.train[-1]),
                    is_backtest=True,
                )
                session.add(run)
                session.flush()  # assign run.id without a full commit per run
                session.add_all(
                    ForecastPoint(
                        run_id=run.id,
                        step=step,
                        predicted=round(float(forecast[step - 1]), 4),
                        lower=round(max(float(forecast[step - 1] - band[step - 1]), 0.0), 4),
                        upper=round(float(forecast[step - 1] + band[step - 1]), 4),
                    )
                    for step in range(1, horizon + 1)
                )
                counts[name] += 1
            session.commit()

        score_pending(session, symbol, interval)

    return counts


def clear_backtests(session: Session, interval: str = "1d") -> None:
    """Drop prior backtest runs for this interval so a re-run doesn't double-count.

    Scoped to `interval`: the daily and intraday backtests now coexist in the
    same tables, so clearing without this filter would wipe one interval's
    results every time the other is recomputed.
    """
    runs = session.exec(
        select(ForecastRun)
        .where(ForecastRun.is_backtest == True)  # noqa: E712
        .where(ForecastRun.interval == interval)
    ).all()
    ids = [r.id for r in runs]
    for point in session.exec(select(ForecastPoint).where(ForecastPoint.run_id.in_(ids))).all():
        session.delete(point)
    for run in runs:
        session.delete(run)
    session.commit()
