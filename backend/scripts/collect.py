"""Live intraday forecast collector.

    .venv/bin/python -m scripts.collect [--symbols ...] [--interval 5m] [--horizon 12] [--every 300] [--once]

Each tick, per symbol: fetch the latest bars and store any new ones, fit
*every* candidate model (`services.forecasters.MODELS`) and log a forecast for
each if a new bar arrived, then score every earlier live forecast whose target
bars now exist (`score_pending`, shared with the backtest harness — see
`services/backtest.py`).

Logging every candidate, not just whichever one `select_model` currently
serves, is what lets the selection change over time: a model that starts
losing after being picked needs live evidence to fall from, and a model that
was passed over needs live evidence to earn a future win.

Runs indefinitely by default; `--once` runs a single tick and exits, for cron
or manual invocation. Off-hours ticks simply find no new bars and log nothing,
so the loop needs no market-hours awareness — it self-regulates.

Never writes synthetic data: a fetch failure is logged and the symbol is
skipped for that tick, exactly like `corpus.py`'s no-fallback rule. Every step
here is idempotent, so a missed or overlapping tick self-heals on the next one.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import numpy as np
from sqlmodel import Session

from app.db import engine, init_db
from app.models import ForecastPoint, ForecastRun
from app.services.backtest import score_pending
from app.services.corpus import CorpusError, fetch_bars, load_series, store_bars
from app.services.forecasters import DEFAULT_TRAIN_BARS, FALLBACK_INTRADAY_TRAIN_BARS, MODELS
from app.services.providers import POPULAR_STOCKS


def _tick(session: Session, symbol: str, interval: str, horizon: int, train_bars: int) -> None:
    try:
        bars = fetch_bars(symbol, period="1d", interval=interval)
    except CorpusError as exc:
        print(f"  {symbol:<6} fetch failed, skipping: {exc}")
        return

    added = store_bars(session, bars)
    series = load_series(session, symbol, interval)

    if added and len(series) >= train_bars + 1:
        train = np.array([b.close for b in series[-train_bars:]], dtype=float)
        logged = []
        for name, forecaster in MODELS.items():
            try:
                forecast, band = forecaster(train, horizon)
            except ValueError as exc:
                print(f"  {symbol:<6} {name} skipped this tick: {exc}")
                continue
            run = ForecastRun(
                model=name,
                symbol=symbol.upper(),
                interval=interval,
                as_of_ts=series[-1].ts,
                horizon=horizon,
                train_days=len(train),
                anchor_price=float(train[-1]),
                is_backtest=False,
            )
            session.add(run)
            session.flush()  # assign run.id without a full commit
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
            logged.append(name)
        session.commit()
        print(f"  {symbol:<6} +{added} bar(s), logged {logged} as of {series[-1].ts}")
    elif added:
        print(
            f"  {symbol:<6} +{added} bar(s), not enough history yet "
            f"({len(series)}/{train_bars + 1})"
        )

    scored = score_pending(session, symbol, interval)
    if scored:
        print(f"  {symbol:<6} scored {scored} pending point(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(POPULAR_STOCKS))
    parser.add_argument("--interval", default="5m")
    parser.add_argument(
        "--horizon", type=int, default=12, help="steps ahead to forecast, in units of --interval"
    )
    parser.add_argument(
        "--train-bars", type=int, default=None, help="bars of history the fit sees (default: interval-dependent)"
    )
    parser.add_argument("--every", type=int, default=300, help="seconds between ticks")
    parser.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    train_bars = args.train_bars or DEFAULT_TRAIN_BARS.get(
        args.interval, FALLBACK_INTRADAY_TRAIN_BARS
    )
    init_db()

    while True:
        started = time.time()
        print(f"\n[{datetime.utcnow().isoformat(timespec='seconds')}Z] tick")
        with Session(engine) as session:
            for symbol in symbols:
                _tick(session, symbol, args.interval, args.horizon, train_bars)
        if args.once:
            return 0
        elapsed = time.time() - started
        time.sleep(max(0.0, args.every - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
