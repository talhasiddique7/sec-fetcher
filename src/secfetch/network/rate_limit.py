from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """
    Simple global rate limiter (shared across requests).

    Enforces an average max rate by spacing requests at 1/max_per_second.
    """

    def __init__(self, max_per_second: float) -> None:
        if max_per_second <= 0:
            raise ValueError("max_per_second must be > 0")
        self._interval = 1.0 / max_per_second
        self._lock = asyncio.Lock()
        self._next_time = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next_time:
                await asyncio.sleep(self._next_time - now)
            now2 = time.monotonic()
            self._next_time = max(self._next_time, now2) + self._interval

