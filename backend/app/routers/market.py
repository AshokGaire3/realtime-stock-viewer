"""Market-data proxy endpoints.

These relay the same data the frontend used to fetch directly, but with the
API keys held server-side and responses cached to respect rate limits.
"""

from fastapi import APIRouter, Query

from app.schemas import ChartData, CryptoData, StockData
from app.services import providers

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/stocks", response_model=list[StockData])
async def stocks() -> list[StockData]:
    return await providers.get_stocks()


@router.get("/quote", response_model=StockData)
async def quote(symbol: str = Query(..., min_length=1)) -> StockData:
    return await providers.get_quote(symbol)


@router.get("/crypto", response_model=list[CryptoData])
async def crypto() -> list[CryptoData]:
    return await providers.get_crypto()


@router.get("/history", response_model=list[ChartData])
async def history(
    symbol: str = Query(..., min_length=1),
    days: int = Query(30, ge=1, le=365),
) -> list[ChartData]:
    return await providers.get_historical(symbol, days)


@router.get("/search", response_model=list[StockData])
async def search(q: str = Query(..., min_length=1)) -> list[StockData]:
    return await providers.search_stocks(q)
