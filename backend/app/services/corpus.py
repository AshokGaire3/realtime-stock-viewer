"""Real historical price corpus — the ground truth for forecast evaluation.

Deliberately separate from `providers.py`. That module serves the live UI and
falls back to synthetic prices so a chart still renders when a provider is
down; this one must never do that. A backtest scored against invented prices
produces an invented accuracy number, so a gap here is an error, not something
to paper over.

Source is yfinance (server-side only, same as every other upstream call).
"""

from __future__ import annotations

from datetime import datetime

import yfinance as yf
from sqlmodel import Session, select

from app.models import PriceBar

SOURCE = "yfinance"

# yfinance enforces lookback caps on sub-daily intervals: ~60 days for 5m/15m/30m/
# 60m/90m, ~7 days for 1m. A `period` past the cap doesn't raise — it silently
# returns a shorter series, which would look like a real (thin) corpus rather
# than a mistake. We refuse instead.
_MAX_PERIOD_DAYS = {"1m": 7, "5m": 60, "15m": 60, "30m": 60, "60m": 60, "90m": 60}


def _period_days(period: str) -> int | None:
    if period.endswith("d"):
        return int(period[:-1])
    if period.endswith("y"):
        return int(period[:-1]) * 365
    if period.endswith("mo"):
        return int(period[:-2]) * 30
    return None


class CorpusError(RuntimeError):
    """Raised when real history could not be fetched. Never fall back."""


def fetch_bars(symbol: str, period: str = "10y", interval: str = "1d") -> list[PriceBar]:
    """Fetch split/dividend-adjusted bars. Raises CorpusError if empty or over yfinance's cap."""
    cap = _MAX_PERIOD_DAYS.get(interval)
    if cap is not None:
        requested = _period_days(period)
        if requested is None or requested > cap:
            raise CorpusError(
                f"period={period!r} exceeds yfinance's {cap}-day lookback cap for "
                f"interval={interval!r}"
            )

    df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        raise CorpusError(
            f"No history returned for {symbol!r} (period={period}, interval={interval})"
        )

    bars = [
        PriceBar(
            symbol=symbol.upper(),
            interval=interval,
            ts=idx.to_pydatetime().replace(tzinfo=None),
            open=float(row.Open),
            high=float(row.High),
            low=float(row.Low),
            close=float(row.Close),
            volume=int(row.Volume),
            source=SOURCE,
        )
        for idx, row in zip(df.index, df.itertuples())
    ]
    return bars


def store_bars(session: Session, bars: list[PriceBar]) -> int:
    """Insert bars, skipping (symbol, interval, ts) already stored. Returns the number added."""
    if not bars:
        return 0
    symbol, interval = bars[0].symbol, bars[0].interval
    existing = set(
        session.exec(
            select(PriceBar.ts)
            .where(PriceBar.symbol == symbol)
            .where(PriceBar.interval == interval)
        ).all()
    )
    fresh = [b for b in bars if b.ts not in existing]
    session.add_all(fresh)
    session.commit()
    return len(fresh)


def load_series(session: Session, symbol: str, interval: str = "1d") -> list[PriceBar]:
    """All stored bars for a symbol at this interval, oldest first."""
    return list(
        session.exec(
            select(PriceBar)
            .where(PriceBar.symbol == symbol.upper())
            .where(PriceBar.interval == interval)
            .order_by(PriceBar.ts)
        ).all()
    )


def coverage(
    session: Session, symbol: str, interval: str = "1d"
) -> tuple[int, datetime | None, datetime | None]:
    """(bar count, first ts, last ts) for a symbol at this interval."""
    series = load_series(session, symbol, interval)
    if not series:
        return 0, None, None
    return len(series), series[0].ts, series[-1].ts
