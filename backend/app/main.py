"""FastAPI application entry point.

Run with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import init_db
from app.routers import market, predictions
from app.services.providers import UnknownSymbolError

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="StockLab API",
    description="Market-data proxy and ML price predictions for StockLab. "
    "Upstream API keys stay server-side; the browser only ever talks to this API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Vercel gives every preview deploy a fresh random hostname, so those origins
    # can't be enumerated in cors_origins. Empty string means "no regex" — passing
    # "" through would match every origin.
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(predictions.router)


@app.exception_handler(UnknownSymbolError)
async def unknown_symbol_handler(request: Request, exc: UnknownSymbolError) -> JSONResponse:
    """One place to turn an unrecognised ticker into a 404 for every route."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
