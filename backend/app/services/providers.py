"""Upstream market-data clients.

All calls use the server-side API keys from settings and pass through the TTL
cache. On any upstream error or missing key we fall back to deterministic mock
data so the app stays usable in demo mode (mirrors the original frontend
behaviour, just moved server-side).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import httpx

from app.config import get_settings
from app.schemas import ChartData, CryptoData, StockData
from app.services.cache import cache

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
FINNHUB_BASE = "https://finnhub.io/api/v1"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

POPULAR_STOCKS = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "NFLX"]

CRYPTO_ID_BY_SYMBOL = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
    "SOL": "solana",
}

# Cache TTLs (seconds)
QUOTE_TTL = 45
LIST_TTL = 60
HISTORY_TTL = 3600

# --- Fallback data (used when a provider errors or no key is configured) ---

FALLBACK_STOCKS: list[StockData] = [
    StockData(symbol="AAPL", name="Apple Inc.", price=175.43, change=2.15, changePercent=1.24, volume=45234567, high=176.80, low=173.20, marketCap=2.78e12),
    StockData(symbol="GOOGL", name="Alphabet Inc.", price=142.56, change=-1.23, changePercent=-0.86, volume=23456789, high=144.20, low=141.80, marketCap=1.80e12),
    StockData(symbol="MSFT", name="Microsoft Corp.", price=378.85, change=5.67, changePercent=1.52, volume=32145698, high=380.45, low=375.20, marketCap=2.81e12),
    StockData(symbol="TSLA", name="Tesla Inc.", price=248.73, change=-8.45, changePercent=-3.29, volume=89765432, high=255.30, low=246.90, marketCap=7.9e11),
    StockData(symbol="AMZN", name="Amazon.com Inc.", price=155.89, change=3.21, changePercent=2.10, volume=54321098, high=157.45, low=153.60, marketCap=1.62e12),
    StockData(symbol="NVDA", name="NVIDIA Corp.", price=875.25, change=15.67, changePercent=1.82, volume=67890123, high=882.40, low=865.30, marketCap=2.15e12),
]

FALLBACK_CRYPTO: list[CryptoData] = [
    CryptoData(id="bitcoin", symbol="btc", name="Bitcoin", current_price=43250.67, price_change_24h=1250.34, price_change_percentage_24h=2.98, market_cap=8.47e11, total_volume=2.35e10, high_24h=43800.0, low_24h=42100.5),
    CryptoData(id="ethereum", symbol="eth", name="Ethereum", current_price=2634.89, price_change_24h=-45.23, price_change_percentage_24h=-1.69, market_cap=3.16e11, total_volume=1.23e10, high_24h=2689.45, low_24h=2598.3),
    CryptoData(id="cardano", symbol="ada", name="Cardano", current_price=0.485, price_change_24h=0.023, price_change_percentage_24h=4.98, market_cap=1.72e10, total_volume=5.68e8, high_24h=0.492, low_24h=0.461),
    CryptoData(id="solana", symbol="sol", name="Solana", current_price=98.34, price_change_24h=5.67, price_change_percentage_24h=6.12, market_cap=4.28e10, total_volume=1.23e9, high_24h=101.23, low_24h=95.78),
]


def _fallback_history(symbol: str, days: int) -> list[ChartData]:
    """Deterministic-ish synthetic history so charts/predictions still work."""
    base = next((s.price for s in FALLBACK_STOCKS if s.symbol == symbol.upper()), 100.0)
    today = datetime.utcnow()
    out: list[ChartData] = []
    for i in range(days, -1, -1):
        d = today - timedelta(days=i)
        trend = (days - i) / max(days, 1)
        wobble = 0.03 * math.sin(i / 3.0)  # smooth, deterministic variation
        price = base * (0.95 + trend * 0.1 + wobble)
        out.append(ChartData(date=d.strftime("%Y-%m-%d"), price=round(price, 2), volume=10_000_000 + i * 100_000))
    return out


# --- Live providers ---

async def _get_stock_quote(client: httpx.AsyncClient, symbol: str) -> StockData | None:
    settings = get_settings()
    cache_key = f"quote:{symbol.upper()}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    # Alpha Vantage first
    try:
        r = await client.get(
            ALPHA_VANTAGE_BASE,
            params={"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": settings.alpha_vantage_api_key},
        )
        data = r.json()
        quote = data.get("Global Quote") or {}
        if quote.get("05. price"):
            result = StockData(
                symbol=quote.get("01. symbol", symbol),
                name=symbol,
                price=float(quote["05. price"]),
                change=float(quote.get("09. change", 0) or 0),
                changePercent=float(str(quote.get("10. change percent", "0")).replace("%", "") or 0),
                volume=int(quote.get("06. volume", 0) or 0),
                high=float(quote.get("03. high", 0) or 0),
                low=float(quote.get("04. low", 0) or 0),
                marketCap=0,
            )
            await cache.set(cache_key, result, QUOTE_TTL)
            return result
    except Exception:  # noqa: BLE001 - upstream is best-effort
        pass

    # Finnhub backup
    if settings.finnhub_api_key:
        try:
            q = await client.get(f"{FINNHUB_BASE}/quote", params={"symbol": symbol, "token": settings.finnhub_api_key})
            p = await client.get(f"{FINNHUB_BASE}/stock/profile2", params={"symbol": symbol, "token": settings.finnhub_api_key})
            quote = q.json()
            profile = p.json()
            if quote.get("c"):
                result = StockData(
                    symbol=symbol,
                    name=profile.get("name", symbol),
                    price=float(quote["c"]),
                    change=float(quote.get("d", 0) or 0),
                    changePercent=float(quote.get("dp", 0) or 0),
                    volume=0,
                    high=float(quote.get("h", 0) or 0),
                    low=float(quote.get("l", 0) or 0),
                    marketCap=float(profile.get("marketCapitalization", 0) or 0) * 1_000_000,
                )
                await cache.set(cache_key, result, QUOTE_TTL)
                return result
        except Exception:  # noqa: BLE001
            pass

    return None


async def get_stocks() -> list[StockData]:
    cache_key = "list:stocks"
    if (hit := await cache.get(cache_key)) is not None:
        return hit
    async with httpx.AsyncClient(timeout=10) as client:
        results: list[StockData] = []
        for sym in POPULAR_STOCKS:
            q = await _get_stock_quote(client, sym)
            if q:
                results.append(q)
    final = results if results else FALLBACK_STOCKS
    await cache.set(cache_key, final, LIST_TTL)
    return final


async def get_quote(symbol: str) -> StockData:
    async with httpx.AsyncClient(timeout=10) as client:
        q = await _get_stock_quote(client, symbol)
    if q:
        return q
    return next(
        (s for s in FALLBACK_STOCKS if s.symbol == symbol.upper()),
        StockData(symbol=symbol.upper(), name=symbol.upper(), price=100.0, change=0, changePercent=0, volume=0, high=100, low=100, marketCap=0),
    )


async def get_crypto() -> list[CryptoData]:
    cache_key = "list:crypto"
    if (hit := await cache.get(cache_key)) is not None:
        return hit
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{COINGECKO_BASE}/coins/markets",
                params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10, "page": 1, "sparkline": "false", "price_change_percentage": "24h"},
            )
            r.raise_for_status()
            coins = r.json()
        result = [
            CryptoData(
                id=c["id"], symbol=c["symbol"], name=c["name"],
                current_price=c.get("current_price") or 0,
                price_change_24h=c.get("price_change_24h") or 0,
                price_change_percentage_24h=c.get("price_change_percentage_24h") or 0,
                market_cap=c.get("market_cap") or 0,
                total_volume=c.get("total_volume") or 0,
                high_24h=c.get("high_24h") or 0,
                low_24h=c.get("low_24h") or 0,
            )
            for c in coins
        ]
        await cache.set(cache_key, result, LIST_TTL)
        return result
    except Exception:  # noqa: BLE001
        return FALLBACK_CRYPTO


async def get_historical(symbol: str, days: int = 30) -> list[ChartData]:
    cache_key = f"history:{symbol.upper()}:{days}"
    if (hit := await cache.get(cache_key)) is not None:
        return hit

    settings = get_settings()
    upper = symbol.upper()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Crypto history via CoinGecko
            if upper in CRYPTO_ID_BY_SYMBOL:
                coin_id = CRYPTO_ID_BY_SYMBOL[upper]
                r = await client.get(
                    f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
                    params={"vs_currency": "usd", "days": days},
                )
                prices = r.json().get("prices", [])
                if prices:
                    result = [
                        ChartData(date=datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d"), price=price, volume=0)
                        for ts, price in prices
                    ]
                    await cache.set(cache_key, result, HISTORY_TTL)
                    return result

            # Stock daily history via Alpha Vantage
            r = await client.get(
                ALPHA_VANTAGE_BASE,
                params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "apikey": settings.alpha_vantage_api_key},
            )
            data = r.json()
            series = data.get("Time Series (Daily)")
            if series:
                items = [
                    ChartData(date=date, price=float(v["4. close"]), volume=int(v["5. volume"]))
                    for date, v in list(series.items())[:days]
                ]
                items.reverse()
                await cache.set(cache_key, items, HISTORY_TTL)
                return items
    except Exception:  # noqa: BLE001
        pass

    result = _fallback_history(symbol, days)
    await cache.set(cache_key, result, HISTORY_TTL)
    return result


async def search_stocks(query: str) -> list[StockData]:
    stocks = await get_stocks()
    q = query.lower()
    return [s for s in stocks if q in s.symbol.lower() or q in s.name.lower()]
