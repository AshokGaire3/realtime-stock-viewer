"""SQLModel tables for paper trading, lesson progress, and forecast evaluation.

Single-user for v1 (no auth); a `user` column is included with a default so
multi-user can be layered on later without a migration headache.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel, UniqueConstraint


class Holding(SQLModel, table=True):
    """Current net position in a symbol (paper trading)."""

    id: int | None = Field(default=None, primary_key=True)
    user: str = Field(default="local", index=True)
    symbol: str = Field(index=True)
    shares: float = 0.0
    avg_cost: float = 0.0


class Trade(SQLModel, table=True):
    """An individual buy/sell, kept for history and P/L auditing."""

    id: int | None = Field(default=None, primary_key=True)
    user: str = Field(default="local", index=True)
    symbol: str = Field(index=True)
    side: str  # "buy" | "sell"
    shares: float
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LessonProgress(SQLModel, table=True):
    """Per-lesson completion state for the guided-learning module."""

    id: int | None = Field(default=None, primary_key=True)
    user: str = Field(default="local", index=True)
    lesson_id: str = Field(index=True)
    completed: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Forecast evaluation ---
#
# These three tables exist to answer "how far ahead can the model forecast, and
# how well". `PriceBar` is the ground-truth corpus; a ForecastRun is one model
# predicting one symbol from one point in time; ForecastPoints are the
# individual day-ahead predictions, scored against the corpus after the fact.


class PriceBar(SQLModel, table=True):
    """One bar of real market history — the ground truth we score against.

    `interval` is "1d" for the daily corpus or a yfinance intraday code
    ("5m", "1m", ...). Prices are split/dividend-adjusted, so a series is
    internally consistent over time (an unadjusted split shows up as a -50%
    bar and would wreck both the fit and the scoring).
    """

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "ts", name="uq_pricebar_symbol_interval_ts"),
    )

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    interval: str = Field(default="1d", index=True)
    ts: datetime = Field(index=True)
    open: float
    high: float
    low: float
    close: float  # adjusted close
    volume: int
    source: str  # provider the bar came from, e.g. "yfinance"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ForecastRun(SQLModel, table=True):
    """One model forecasting one symbol as of one point in time.

    `as_of_ts` is the last bar the model was allowed to see. Everything after
    it is the future as far as this run is concerned — that invariant is what
    keeps a backtest honest, and it is enforced in the harness. `horizon` is a
    step count in units of `interval`, not calendar days.
    """

    id: int | None = Field(default=None, primary_key=True)
    model: str = Field(index=True)  # "linear-trend" | "random-walk" | "drift"
    symbol: str = Field(index=True)
    interval: str = Field(default="1d", index=True)
    as_of_ts: datetime = Field(index=True)
    horizon: int  # steps ahead, in units of `interval`
    train_days: int  # how many bars the fit actually saw
    anchor_price: float  # close at as_of_ts; baseline for % errors
    is_backtest: bool = True  # False once logged from a live /api/predict call
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ForecastPoint(SQLModel, table=True):
    """A single step-ahead prediction and, once known, what actually happened."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="forecastrun.id", index=True)
    step: int = Field(index=True)  # bars ahead: 1..horizon, in units of run.interval
    # Filled in by scoring, from the bar it actually matched. Null until then —
    # scoring is by ordinal step, not by a precomputed calendar date, so this
    # carries no meaning before the point is scored.
    target_ts: datetime | None = Field(default=None, index=True)
    predicted: float
    lower: float
    upper: float
    actual: float | None = None
    abs_error: float | None = None
    pct_error: float | None = None  # abs_error / actual, as a fraction
    in_band: bool | None = None  # did actual land inside [lower, upper]
    direction_hit: bool | None = None  # did we get the sign of the move right
