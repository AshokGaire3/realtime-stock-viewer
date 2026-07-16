"""ML price-prediction endpoints (Phase 2)."""

from fastapi import APIRouter, Query

from app.schemas import PredictionResult
from app.services import predictions

router = APIRouter(prefix="/api", tags=["predictions"])


@router.get("/predict", response_model=PredictionResult)
async def predict(
    symbol: str = Query(..., min_length=1),
    horizon: int = Query(7, ge=1, le=30),
) -> PredictionResult:
    return await predictions.get_prediction(symbol, horizon)
