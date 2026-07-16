"""A tiny async-safe TTL cache.

Response caching is how we stay under the free-tier rate limits of Alpha
Vantage / Finnhub / CoinGecko. Swap this for Redis later if we scale out to
multiple backend instances.
"""

import time
from typing import Any

from anyio import Lock


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        async with self._lock:
            self._store[key] = (time.monotonic() + ttl_seconds, value)


# Shared process-wide cache instance.
cache = TTLCache()
