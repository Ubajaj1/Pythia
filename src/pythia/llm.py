"""LLM client abstraction and Ollama implementation."""

from __future__ import annotations

import json
import logging
import time
from typing import Protocol

import httpx

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM backends. Implement generate() to swap providers."""

    async def generate(self, prompt: str, system: str | None = None) -> dict: ...


class OllamaClient:
    """Thin async HTTP wrapper for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        logger.info(
            "LLM call model=%s prompt_chars=%d has_system=%s",
            self.model, len(prompt), system is not None,
        )
        logger.debug("LLM system:\n%s", system or "(none)")
        logger.debug("LLM prompt:\n%s", prompt)

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if system:
            payload["system"] = system

        t0 = time.perf_counter()
        response = await self._http.post(
            f"{self.base_url}/api/generate", json=payload
        )
        response.raise_for_status()
        raw = response.json()["response"]
        latency_ms = round((time.perf_counter() - t0) * 1000)

        logger.info("LLM response latency_ms=%d response_chars=%d", latency_ms, len(raw))
        logger.debug("LLM raw response:\n%s", raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("LLM response is not valid JSON — retrying model=%s", self.model)
            logger.debug("LLM invalid response was:\n%s", raw)
            payload["prompt"] = (
                "Your previous response was not valid JSON. "
                "Respond with ONLY valid JSON.\n\n" + prompt
            )
            t0 = time.perf_counter()
            response = await self._http.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            raw = response.json()["response"]
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info("LLM retry response latency_ms=%d response_chars=%d", latency_ms, len(raw))
            logger.debug("LLM retry raw response:\n%s", raw)
            return json.loads(raw)

    async def close(self):
        await self._http.aclose()


def build_llm_client(
    provider: str | None = None,
    ollama_url: str | None = None,
    model: str | None = None,
) -> "OllamaClient":
    """Return the right LLM client based on provider arg or env vars.

    Priority: explicit provider arg > ANTHROPIC_API_KEY > GROQ_API_KEY > OPENAI_API_KEY > Ollama.
    """
    from pythia.config import (
        ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
        GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL,
        OLLAMA_BASE_URL, OLLAMA_MODEL,
        OPENAI_API_KEY, OPENAI_MODEL,
    )

    effective_provider = provider or (
        "anthropic" if ANTHROPIC_API_KEY else
        "groq"      if GROQ_API_KEY else
        "openai"    if OPENAI_API_KEY else
        "ollama"
    )

    if effective_provider == "anthropic":
        from pythia.anthropic_client import AnthropicClient
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY env var is not set")
        logger.info("LLM provider=anthropic model=%s", model or ANTHROPIC_MODEL)
        return AnthropicClient(api_key=ANTHROPIC_API_KEY, model=model or ANTHROPIC_MODEL)  # type: ignore[return-value]

    if effective_provider == "groq":
        from pythia.openai_client import OpenAIClient
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY env var is not set")
        logger.info("LLM provider=groq model=%s", model or GROQ_MODEL)
        return OpenAIClient(api_key=GROQ_API_KEY, model=model or GROQ_MODEL, base_url=GROQ_BASE_URL)  # type: ignore[return-value]

    if effective_provider == "openai":
        from pythia.openai_client import OpenAIClient
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY env var is not set")
        logger.info("LLM provider=openai model=%s", model or OPENAI_MODEL)
        return OpenAIClient(api_key=OPENAI_API_KEY, model=model or OPENAI_MODEL)  # type: ignore[return-value]

    logger.info("LLM provider=ollama url=%s model=%s", ollama_url or OLLAMA_BASE_URL, model or OLLAMA_MODEL)
    return OllamaClient(base_url=ollama_url or OLLAMA_BASE_URL, model=model or OLLAMA_MODEL)
