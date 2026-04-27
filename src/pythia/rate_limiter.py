"""Token-bucket rate limiter for LLM API calls.

Prevents 429s by throttling at the source rather than retrying after the fact.
Each call acquires a token before firing. If the bucket is empty, the caller
sleeps until a token is available.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Async token-bucket rate limiter.

    Args:
        rpm: Maximum requests per minute. 0 or None = unlimited.
    """

    def __init__(self, rpm: int | None = None):
        self.rpm = rpm or 0
        if self.rpm > 0:
            self._interval = 60.0 / self.rpm  # seconds between tokens
        else:
            self._interval = 0.0
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        if self._interval <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                wait = self._interval - elapsed
                logger.debug("Rate limiter: waiting %.2fs (rpm=%d)", wait, self.rpm)
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
