"""Token-bucket rate limiter for LLM API calls.

Prevents 429s by throttling at the source rather than retrying after the fact.
Each call acquires a token before firing. If the bucket is empty, the caller
sleeps until a token is available. Properly handles concurrent callers by
reserving future time slots.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Async token-bucket rate limiter with proper concurrent queuing.

    When multiple coroutines call acquire() simultaneously, each one reserves
    the next available time slot. The first caller gets the current slot,
    the second gets current + interval, the third gets current + 2*interval, etc.

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
        self._next_slot = 0.0  # monotonic time of next available slot

    async def acquire(self) -> None:
        """Reserve the next available time slot and wait until it arrives."""
        if self._interval <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            # If next_slot is in the past, reset to now
            if self._next_slot <= now:
                self._next_slot = now
            
            # This caller's slot is the current next_slot
            my_slot = self._next_slot
            # Advance next_slot for the next caller
            self._next_slot = my_slot + self._interval

            # How long until our slot?
            wait = my_slot - now
            if wait > 0:
                logger.debug(
                    "Rate limiter: queued, waiting %.2fs (rpm=%d, slot=%.2f)",
                    wait, self.rpm, my_slot,
                )

        # Sleep outside the lock so other callers can reserve their slots
        if wait > 0:
            await asyncio.sleep(wait)
