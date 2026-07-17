"""SQLModel tables for paper trading, lesson progress, and forecast evaluation.

Single-user for v1 (no auth); a `user` column is included with a default so
multi-user can be layered on later without a migration headache.
"""

from datetime import date as Date
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
    """One daily bar of real market history — the ground truth we score against.

    Prices are split/dividend-adjusted, so a series is internally consistent
    over time (an unadjusted split shows up as a -50% day and would wreck both
    the fit and the scoring).
    """

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_pricebar_symbol_date"),)

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    date: Date = Field(index=True)
    open: float
    high: float
    low: float
    close: float  # adjusted close
    volume: int
    source: str  # provider the bar came from, e.g. "yfinance"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class ForecastRun(SQLModel, table=True):
    """One model forecasting one symbol as of one date.

    `as_of_date` is the last bar the model was allowed to see. Everything after
    it is the future as far as this run is concerned — that invariant is what
    keeps a backtest honest, and it is asserted in the harness.
    """

    id: int | None = Field(default=None, primary_key=True)
    model: str = Field(index=True)  # "linear-trend" | "random-walk" | "drift"
    symbol: str = Field(index=True)
    as_of_date: Date = Field(index=True)
    horizon_days: int
    train_days: int  # how many bars the fit actually saw
    anchor_price: float  # close on as_of_date; baseline for % errors
    is_backtest: bool = True  # False once we log live /api/predict calls
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ForecastPoint(SQLModel, table=True):
    """A single day-ahead prediction and, once known, what actually happened."""

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="forecastrun.id", index=True)
    step: int = Field(index=True)  # trading days ahead: 1..horizon
    target_date: Date = Field(index=True)
    predicted: float
    lower: float
    upper: float
    # Filled in by scoring once the target date has real data. Null means
    # unscored (still in the future, or the corpus has no bar for that day).
    actual: float | None = None
    abs_error: float | None = None
    pct_error: float | None = None  # abs_error / actual, as a fraction
    in_band: bool | None = None  # did actual land inside [lower, upper]
    direction_hit: bool | None = None  # did we get the sign of the move right
