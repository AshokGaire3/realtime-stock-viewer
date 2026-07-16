"""SQLModel tables for paper trading and lesson progress.

Single-user for v1 (no auth); a `user` column is included with a default so
multi-user can be layered on later without a migration headache.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


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
