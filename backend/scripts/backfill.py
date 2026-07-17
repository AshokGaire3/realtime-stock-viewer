"""Load real daily price history into the corpus.

    .venv/bin/python -m scripts.backfill [--symbols AAPL,MSFT] [--period 10y]

Idempotent: re-running only inserts dates not already stored.
"""

from __future__ import annotations

import argparse
import sys

from sqlmodel import Session

from app.db import engine, init_db
from app.services.corpus import CorpusError, coverage, fetch_bars, store_bars
from app.services.providers import POPULAR_STOCKS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(POPULAR_STOCKS))
    parser.add_argument("--period", default="10y")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    init_db()

    failures: list[str] = []
    with Session(engine) as session:
        for symbol in symbols:
            try:
                bars = fetch_bars(symbol, args.period)
                added = store_bars(session, bars)
            except CorpusError as exc:
                print(f"  {symbol:<6} FAILED: {exc}")
                failures.append(symbol)
                continue
            n, first, last = coverage(session, symbol)
            print(f"  {symbol:<6} +{added:<5} stored={n:<6} {first} -> {last}")

    if failures:
        print(f"\nFAILED for {len(failures)} symbol(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"\nCorpus ready for {len(symbols)} symbols.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
