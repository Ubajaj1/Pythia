"""OpenAI-compatible LLM client — works for OpenAI, Groq, and any compatible API."""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from pythia.config import OPENAI_MODEL

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_MAX_RETRIES = 6


class OpenAIClient:
    """Calls any OpenAI-compatible chat completions endpoint with JSON mode enforced."""

    def __init__(
        self,
        api_key: str,
        model: str = OPENAI_MODEL,
        base_url: str = _OPENAI_URL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        logger.info(
            "LLM call model=%s prompt_chars=%d has_system=%s",
            self.model, len(prompt), system is not None,
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
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(_MAX_RETRIES):
            t0 = time.perf_counter()
            response = await self._http.post(self.base_url, json=payload, headers=headers)

            if response.status_code == 429:
                wait = float(response.headers.get("retry-after", 2 ** attempt))
                logger.warning("Rate limited (429) — waiting %.1fs before retry %d/%d", wait, attempt + 1, _MAX_RETRIES)
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            latency_ms = round((time.perf_counter() - t0) * 1000)

            logger.info("LLM response latency_ms=%d response_chars=%d", latency_ms, len(raw))
            logger.debug("LLM raw response:\n%s", raw)
            return json.loads(raw)

        raise RuntimeError(f"Exceeded {_MAX_RETRIES} retries due to rate limiting")

    async def close(self) -> None:
        await self._http.aclose()
