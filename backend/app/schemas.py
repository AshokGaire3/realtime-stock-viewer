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
