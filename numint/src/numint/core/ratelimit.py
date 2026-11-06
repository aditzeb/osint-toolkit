"""Per-provider async rate limiting so free-tier quotas are respected.

A single shared limiter would throttle unrelated providers against each other,
so each provider name gets its own token-bucket keyed limiter.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Token-bucket limiter keyed by provider name."""

    def __init__(self, rate_per_sec: float) -> None:
        self._rate = max(rate_per_sec, 0.1)
        self._min_interval = 1.0 / self._rate
        self._last: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str) -> None:
        async with self._locks[key]:
            now = time.monotonic()
            wait = self._last[key] + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[key] = time.monotonic()
