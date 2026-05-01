"""Tests for the token-bucket rate limiter."""

import asyncio
import time
import pytest
from pythia.rate_limiter import RateLimiter


class TestRateLimiter:
    async def test_unlimited_does_not_block(self):
        rl = RateLimiter(rpm=0)
        t0 = time.monotonic()
        for _ in range(10):
            await rl.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1  # should be near-instant

    async def test_none_rpm_is_unlimited(self):
        rl = RateLimiter(rpm=None)
        t0 = time.monotonic()
        for _ in range(10):
            await rl.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1

    async def test_rate_limits_calls(self):
        # 600 RPM = 10 per second = 0.1s between calls
        rl = RateLimiter(rpm=600)
        t0 = time.monotonic()
        await rl.acquire()  # first call — instant
        await rl.acquire()  # second call — should wait ~0.1s
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.08  # allow some timing slack

    async def test_high_rpm_is_fast(self):
        # 6000 RPM = 100 per second = 0.01s between calls
        rl = RateLimiter(rpm=6000)
        t0 = time.monotonic()
        for _ in range(5):
            await rl.acquire()
        elapsed = time.monotonic() - t0
        # 5 calls at 0.01s spacing = ~0.04s
        assert elapsed < 0.2

    async def test_low_rpm_enforces_spacing(self):
        # 30 RPM = 0.5 per second = 2s between calls
        rl = RateLimiter(rpm=30)
        t0 = time.monotonic()
        await rl.acquire()
        await rl.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed >= 1.8  # ~2s between calls
