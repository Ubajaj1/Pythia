"""Anthropic LLM client — drop-in replacement for OllamaClient."""

from __future__ import annotations

import json
import logging
import re
import time

import httpx

from pythia.config import ANTHROPIC_MODEL

logger = logging.getLogger(__name__)

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicClient:
    """Calls Anthropic Messages API and parses JSON from the response text."""

    def __init__(
        self,
        api_key: str,
        model: str = ANTHROPIC_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        logger.info(
            "LLM call provider=anthropic model=%s prompt_chars=%d has_system=%s seed=%s",
            self.model, len(prompt), system is not None, seed,
        )
        if seed is not None:
            logger.debug("Anthropic does not support seed parameter — ignoring seed=%d", seed)
        logger.debug("LLM system:\n%s", system or "(none)")
        logger.debug("LLM prompt:\n%s", prompt)

        payload: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        t0 = time.perf_counter()
        response = await self._http.post(
            _API_URL,
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": _API_VERSION,
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        raw = response.json()["content"][0]["text"]
        latency_ms = round((time.perf_counter() - t0) * 1000)

        logger.info("LLM response latency_ms=%d response_chars=%d", latency_ms, len(raw))
        logger.debug("LLM raw response:\n%s", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Anthropic has no json_mode — extract JSON block from prose if needed
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                logger.warning("Anthropic response wrapped in prose — extracted JSON block")
                return json.loads(match.group())
            logger.warning("Anthropic response could not be parsed as JSON model=%s", self.model)
            return {}

    async def close(self) -> None:
        await self._http.aclose()
