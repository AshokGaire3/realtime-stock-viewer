"""Pydantic response models. Field names mirror the frontend TypeScript types
in `frontend/src/types/financial.ts` so the client needs no reshaping.

Every payload that can be synthesised carries a `source` so the UI can never
present demo data as a live quote.
"""

from typing import Literal

from pydantic import BaseModel

# "live"     - fetched from an upstream provider
# "fallback" - synthetic demo data (provider errored, rate-limited, or no key)
Source = Literal["live", "fallback"]


class StockData(BaseModel):
    symbol: str
    name: str
    price: float
    change: float
    changePercent: float
    volume: int
    marketCap: float | None = 0
    high: float
    low: float
    # Per-item: a list may mix live and fallback quotes when a provider only
    # partially responds (e.g. the Alpha Vantage demo key serves MSFT only).
    source: Source = "live"


class ChartData(BaseModel):
    date: str
    price: float
    volume: int | None = 0


class HistorySeries(BaseModel):
    """A price series. `source` applies to the whole series, not per point."""

    symbol: str
    source: Source
    points: list[ChartData]


class CryptoData(BaseModel):
    id: str
    symbol: str
    name: str
    current_price: float
    price_change_24h: float
    price_change_percentage_24h: float
    market_cap: float
    total_volume: float
    high_24h: float
    low_24h: float
    # Upstream logo URL; absent for synthetic fallback coins.
    image: str | None = None
    source: Source = "live"


class Indicators(BaseModel):
    """Technical indicators derived from recent price history."""

    sma_20: float | None = None
    sma_50: float | None = None
    rsi_14: float | None = None
    volatility: float | None = None  # annualized stdev of daily returns


class PredictionPoint(BaseModel):
    date: str
    predicted: float
    lower: float  # lower bound of the confidence band
    upper: float  # upper bound of the confidence band


class ModelAccuracy(BaseModel):
    """How wrong this model actually was, measured out-of-sample.

    Sourced from the walk-forward backtest, not from the fit. An in-sample R^2
    says how well a line was drawn through prices we already had; it says
    nothing about tomorrow, and presenting it as "confidence" overstates the
    model. These numbers are what the model scored against real history.
    """

    horizon_days: int
    mape: float  # typical error at this horizon, percent
    baseline_mape: float  # random-walk ("price won't change") over the same origins
    beats_baseline: bool  # does the model actually improve on assuming no change?
    n_forecasts: int  # sample size behind these figures


class PredictionResult(BaseModel):
    symbol: str
    model: str  # which model produced the forecast, e.g. "linear-trend"
    generated_at: str
    current_price: float
    horizon_days: int
    trend: str  # "up" | "down" | "flat"
    # Measured accuracy, or None when no backtest has been run yet. Deliberately
    # not a "confidence" score: we report the error we observed, not a
    # self-assessment derived from the model's own fit.
    accuracy: ModelAccuracy | None = None
    forecast: list[PredictionPoint]
    indicators: Indicators
    # Whether the underlying history was real. A forecast fitted on synthetic
    # demo prices is meaningless as a market signal and must say so.
    data_source: Source
    disclaimer: str = (
        "Forecasts are statistical extrapolations for educational use only, "
        "not financial advice."
    )
