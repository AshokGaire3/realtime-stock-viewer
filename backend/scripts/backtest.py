"""Walk-forward backtest of the forecast models, scored against the corpus.

    .venv/bin/python -m scripts.backtest [--symbols ...] [--horizon 30] [--stride 5]

Wipes prior backtest runs and recomputes, so re-running is safe.
"""

from __future__ import annotations

import argparse
import time

from sqlmodel import Session

from app.db import engine, init_db
from app.services.backtest import clear_backtests, run_backtest
from app.services.evaluation import format_report, metrics_by_horizon
from app.services.providers import POPULAR_STOCKS

REPORT_STEPS = [1, 5, 10, 20, 30]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(POPULAR_STOCKS))
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--stride", type=int, default=5, help="bars between origins")
    parser.add_argument(
        "--interval", default="1d", help="corpus interval to backtest against, e.g. 1d, 5m"
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    init_db()

    with Session(engine) as session:
        print(f"Clearing prior backtest runs for interval={args.interval!r}...")
        clear_backtests(session, interval=args.interval)

        started = time.time()
        counts = run_backtest(
            session, symbols, horizon=args.horizon, stride=args.stride, interval=args.interval
        )
        elapsed = time.time() - started
        total = sum(counts.values())
        print(f"Ran {total} forecasts across {len(symbols)} symbols in {elapsed:.1f}s")
        for model, n in counts.items():
            print(f"  {model:<14} {n:>6} runs")

        # Small horizons (e.g. an intraday 1hr = 12 five-minute steps) are cheap
        # enough to report every step; large ones fall back to the sparse curve.
        steps = (
            list(range(1, args.horizon + 1))
            if args.horizon <= 15
            else [s for s in REPORT_STEPS if s <= args.horizon]
        )
        metrics = metrics_by_horizon(session, steps=steps, interval=args.interval)
        print("\n" + format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
