"""ML price-prediction endpoints."""

from fastapi import APIRouter, Query

from app.schemas import PredictionResult, TodayShowcase
from app.services import predictions

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predict", response_model=PredictionResult)
async def predict(
    symbol: str = Query(..., min_length=1),
    horizon: int = Query(7, ge=1, le=30),
    interval: str = Query("1d", pattern="^(1d|60m)$"),
) -> PredictionResult:
    return await predictions.get_prediction(symbol, horizon, interval)


@router.get("/predict/today", response_model=TodayShowcase)
async def predict_today(
    symbol: str = Query(..., min_length=1),
    days: int = Query(1, ge=1, le=7),
) -> TodayShowcase:
    """Today's hourly bars so far, an hourly forecast spanning `days` trading
    days, and every prediction already labeled against reality today.
    """
    return await predictions.get_today_showcase(symbol, days=days)
