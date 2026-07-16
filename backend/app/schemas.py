"""Pydantic response models. Field names mirror the frontend TypeScript types
in `frontend/src/types/financial.ts` so the client needs no reshaping.
"""

from pydantic import BaseModel


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


class ChartData(BaseModel):
    date: str
    price: float
    volume: int | None = 0


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


class PredictionResult(BaseModel):
    symbol: str
    model: str  # which model produced the forecast, e.g. "linear-trend"
    generated_at: str
    current_price: float
    horizon_days: int
    trend: str  # "up" | "down" | "flat"
    confidence: float  # 0..1, degrades as the band widens / fit is poor
    forecast: list[PredictionPoint]
    indicators: Indicators
    disclaimer: str = (
        "Forecasts are statistical extrapolations for educational use only, "
        "not financial advice."
    )
