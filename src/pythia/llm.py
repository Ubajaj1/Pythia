"""LLM client abstraction and Ollama implementation."""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL


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
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if system:
            payload["system"] = system

        response = await self._http.post(
            f"{self.base_url}/api/generate", json=payload
        )
        response.raise_for_status()
        raw = response.json()["response"]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # One retry with explicit JSON instruction
            payload["prompt"] = (
                "Your previous response was not valid JSON. "
                "Respond with ONLY valid JSON.\n\n" + prompt
            )
            response = await self._http.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            raw = response.json()["response"]
            return json.loads(raw)

    async def close(self):
        await self._http.aclose()
