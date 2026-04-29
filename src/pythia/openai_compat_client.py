"""OpenAI-compatible LLM client — works for OpenAI, Groq, and any compatible API.

Named 'compat' because it speaks the OpenAI wire protocol, not because
it's tied to OpenAI. Groq, Together, Fireworks, etc. all use this format.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from pythia.config import OPENAI_MODEL
from pythia.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MAX_RETRIES = 10


class OpenAICompatClient:
    """Calls any OpenAI-compatible chat completions endpoint with JSON mode enforced.

    Args:
        api_key: Bearer token for the API.
        model: Model identifier (e.g. "gpt-4o-mini", "llama-3.3-70b-versatile").
        base_url: Chat completions endpoint URL.
        rpm: Requests per minute limit. 0 = unlimited. Prevents 429s at the source.
        provider_name: Human-readable name for logging (e.g. "groq", "openai").
    """

    def __init__(
        self,
        api_key: str,
        model: str = OPENAI_MODEL,
        base_url: str = _OPENAI_URL,
        http_client: httpx.AsyncClient | None = None,
        rpm: int = 0,
        provider_name: str = "openai-compat",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider_name = provider_name
        self._http = http_client or httpx.AsyncClient(timeout=120.0)
        self._rate_limiter = RateLimiter(rpm=rpm)

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        logger.info(
            "LLM call provider=%s model=%s prompt_chars=%d has_system=%s seed=%s",
            self.provider_name, self.model, len(prompt), system is not None, seed,
        )
        logger.debug("LLM system:\n%s", system or "(none)")
        logger.debug("LLM prompt:\n%s", prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if seed is not None:
            payload["seed"] = seed
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(_MAX_RETRIES):
            # Throttle before sending — prevents 429s instead of reacting to them
            await self._rate_limiter.acquire()

            t0 = time.perf_counter()
            try:
                response = await self._http.post(self.base_url, json=payload, headers=headers)
            except httpx.ConnectError:
                raise ConnectionError(
                    f"Cannot connect to {self.provider_name} at {self.base_url}"
                ) from None

            if response.status_code == 429:
                # Safety net — rate limiter should prevent this, but APIs can be unpredictable
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    wait = float(retry_after)
                else:
                    wait = min(2 ** attempt, 60)  # cap at 60s
                logger.warning(
                    "Rate limited (429) provider=%s — waiting %.1fs (attempt %d/%d)",
                    self.provider_name, wait, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            latency_ms = round((time.perf_counter() - t0) * 1000)

            logger.info(
                "LLM response provider=%s latency_ms=%d response_chars=%d",
                self.provider_name, latency_ms, len(raw),
            )
            logger.debug("LLM raw response:\n%s", raw)
            return json.loads(raw)

        raise RuntimeError(
            f"Exceeded {_MAX_RETRIES} retries due to rate limiting on {self.provider_name} "
            f"(model={self.model}). Consider using a model with higher RPM limits."
        )

    async def close(self) -> None:
        await self._http.aclose()
