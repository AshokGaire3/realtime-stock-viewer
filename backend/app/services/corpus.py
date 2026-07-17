"""Real historical price corpus — the ground truth for forecast evaluation.

Deliberately separate from `providers.py`. That module serves the live UI and
falls back to synthetic prices so a chart still renders when a provider is
down; this one must never do that. A backtest scored against invented prices
produces an invented accuracy number, so a gap here is an error, not something
to paper over.

Source is yfinance (server-side only, same as every other upstream call).
"""

from __future__ import annotations

from datetime import date as Date

import yfinance as yf
from sqlmodel import Session, select

from app.models import PriceBar

SOURCE = "yfinance"


class CorpusError(RuntimeError):
    """Raised when real history could not be fetched. Never fall back."""


def fetch_bars(symbol: str, period: str = "10y") -> list[PriceBar]:
    """Fetch split/dividend-adjusted daily bars. Raises CorpusError if empty."""
    df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if df.empty:
        raise CorpusError(f"No history returned for {symbol!r} (period={period})")

    bars = [
        PriceBar(
            symbol=symbol.upper(),
            date=idx.date(),
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
    """Insert bars, skipping dates already stored. Returns the number added."""
    if not bars:
        return 0
    symbol = bars[0].symbol
    existing = set(
        session.exec(select(PriceBar.date).where(PriceBar.symbol == symbol)).all()
    )
    fresh = [b for b in bars if b.date not in existing]
    session.add_all(fresh)
    session.commit()
    return len(fresh)


def load_series(session: Session, symbol: str) -> list[PriceBar]:
    """All stored bars for a symbol, oldest first."""
    return list(
        session.exec(
            select(PriceBar).where(PriceBar.symbol == symbol.upper()).order_by(PriceBar.date)
        ).all()
    )


def coverage(session: Session, symbol: str) -> tuple[int, Date | None, Date | None]:
    """(bar count, first date, last date) for a symbol."""
    series = load_series(session, symbol)
    if not series:
        return 0, None, None
    return len(series), series[0].date, series[-1].date
