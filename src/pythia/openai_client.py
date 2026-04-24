"""OpenAI LLM client — drop-in replacement for OllamaClient."""

from __future__ import annotations

import json
import logging
import time

import httpx

from pythia.config import OPENAI_MODEL

logger = logging.getLogger(__name__)

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIClient:
    """Calls OpenAI chat completions with JSON mode enforced."""

    def __init__(
        self,
        api_key: str,
        model: str = OPENAI_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        logger.info(
            "LLM call provider=openai model=%s prompt_chars=%d has_system=%s",
            self.model, len(prompt), system is not None,
        )
        logger.debug("LLM system:\n%s", system or "(none)")
        logger.debug("LLM prompt:\n%s", prompt)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        t0 = time.perf_counter()
        response = await self._http.post(
            _API_URL,
            json={
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        latency_ms = round((time.perf_counter() - t0) * 1000)

        logger.info("LLM response latency_ms=%d response_chars=%d", latency_ms, len(raw))
        logger.debug("LLM raw response:\n%s", raw)
        return json.loads(raw)

    async def close(self) -> None:
        await self._http.aclose()
