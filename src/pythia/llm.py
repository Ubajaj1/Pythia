"""LLM client abstraction and Ollama implementation."""

from __future__ import annotations

import json
import logging
import time
from typing import Protocol

import httpx

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from pythia.usage import record_usage

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """Protocol for LLM backends. Implement generate() to swap providers."""

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict: ...


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

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        logger.info(
            "LLM call model=%s prompt_chars=%d has_system=%s seed=%s",
            self.model, len(prompt), system is not None, seed,
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
        if seed is not None:
            # Ollama supports seed via the options object
            payload["options"] = {"seed": seed}

        try:
            t0 = time.perf_counter()
            response = await self._http.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Is Ollama running? Start it with: ollama serve"
            ) from None
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}. "
                f"Is model '{self.model}' pulled? Try: ollama pull {self.model}"
            ) from None

        data = response.json()
        raw = data["response"]
        record_usage(self.model, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0)))
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
            try:
                t0 = time.perf_counter()
                response = await self._http.post(
                    f"{self.base_url}/api/generate", json=payload
                )
                response.raise_for_status()
            except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
                raise RuntimeError(f"Ollama retry failed: {exc}") from None

            data = response.json()
            raw = data["response"]
            record_usage(self.model, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0)))
            latency_ms = round((time.perf_counter() - t0) * 1000)
            logger.info("LLM retry response latency_ms=%d response_chars=%d", latency_ms, len(raw))
            logger.debug("LLM retry raw response:\n%s", raw)
            return json.loads(raw)

    async def close(self):
        await self._http.aclose()


# --- Provider-aware RPM defaults ---
# These are conservative defaults based on free-tier limits.
# Override via GROQ_RPM / OPENAI_RPM env vars if you have higher limits.

_GROQ_RPM_BY_MODEL = {
    # Current Groq models. The free tier also caps each at ~8k tokens/min,
    # which binds before RPM: a 5-agent, 8-tick run takes about 15 minutes.
    "openai/gpt-oss-120b": 30,
    "openai/gpt-oss-20b": 30,
    # Retired by Groq in 2026; kept so explicit overrides still get a sane RPM.
    "llama-3.3-70b-versatile": 30,
    "llama-3.1-70b-versatile": 30,
    "llama-3.1-8b-instant": 6000,
    "llama3-8b-8192": 6000,
    "llama3-70b-8192": 30,
    "gemma2-9b-it": 30,
    "mixtral-8x7b-32768": 30,
}
_OPENAI_DEFAULT_RPM = 500  # tier-1 default; most paid accounts get 500+


def _groq_rpm(model: str) -> int:
    """Look up Groq RPM for a model, defaulting to 30 (safest)."""
    import os
    env_rpm = os.getenv("GROQ_RPM")
    if env_rpm:
        return int(env_rpm)
    return _GROQ_RPM_BY_MODEL.get(model, 30)


def build_llm_client(
    provider: str | None = None,
    ollama_url: str | None = None,
    model: str | None = None,
) -> LLMClient:
    """Return the right LLM client based on provider arg or env vars.

    Priority: explicit provider arg > ANTHROPIC_API_KEY > GROQ_API_KEY > OPENAI_API_KEY > Ollama.
    """
    import os
    from pythia.config import (
        ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_RPM,
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
        logger.info(
            "LLM provider=anthropic model=%s rpm=%d",
            model or ANTHROPIC_MODEL, ANTHROPIC_RPM,
        )
        return AnthropicClient(
            api_key=ANTHROPIC_API_KEY,
            model=model or ANTHROPIC_MODEL,
            rpm=ANTHROPIC_RPM,
        )

    if effective_provider == "groq":
        from pythia.openai_compat_client import OpenAICompatClient
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY env var is not set")
        effective_model = model or GROQ_MODEL
        rpm = _groq_rpm(effective_model)
        logger.info("LLM provider=groq model=%s rpm=%d", effective_model, rpm)
        return OpenAICompatClient(
            api_key=GROQ_API_KEY, model=effective_model,
            base_url=GROQ_BASE_URL, rpm=rpm, provider_name="groq",
        )

    if effective_provider == "openai":
        from pythia.openai_compat_client import OpenAICompatClient
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY env var is not set")
        effective_model = model or OPENAI_MODEL
        rpm = int(os.getenv("OPENAI_RPM", str(_OPENAI_DEFAULT_RPM)))
        logger.info("LLM provider=openai model=%s rpm=%d", effective_model, rpm)
        return OpenAICompatClient(
            api_key=OPENAI_API_KEY, model=effective_model,
            rpm=rpm, provider_name="openai",
        )

    logger.info("LLM provider=ollama url=%s model=%s", ollama_url or OLLAMA_BASE_URL, model or OLLAMA_MODEL)
    return OllamaClient(base_url=ollama_url or OLLAMA_BASE_URL, model=model or OLLAMA_MODEL)


def parse_model_spec(spec: str) -> tuple[str, str]:
    """Split "provider:model" into its parts."""
    provider, sep, model = spec.partition(":")
    if not sep or not provider or not model:
        raise ValueError(f"Model spec must look like 'provider:model', got {spec!r}")
    return provider, model


def build_role_clients(
    provider: str | None = None,
    ollama_url: str | None = None,
    model: str | None = None,
) -> tuple[LLMClient, LLMClient | None]:
    """Return (main, tick) clients.

    main runs analysis, generation, and summaries; tick runs per-agent turns.
    Priority: PYTHIA_MAIN_MODEL / PYTHIA_TICK_MODEL env specs > provider defaults.
    tick is None when one client should do everything (explicit --model, Ollama, OpenAI).
    """
    import os
    from pythia import config

    main_spec = os.getenv("PYTHIA_MAIN_MODEL")
    tick_spec = os.getenv("PYTHIA_TICK_MODEL")

    if main_spec:
        p, m = parse_model_spec(main_spec)
        main = build_llm_client(provider=p, ollama_url=ollama_url, model=m)
    else:
        main = build_llm_client(provider=provider, ollama_url=ollama_url, model=model)

    if tick_spec:
        p, m = parse_model_spec(tick_spec)
        return main, build_llm_client(provider=p, ollama_url=ollama_url, model=m)
    if model or main_spec:
        return main, None

    effective = provider or (
        "anthropic" if config.ANTHROPIC_API_KEY else
        "groq" if config.GROQ_API_KEY else
        "openai" if config.OPENAI_API_KEY else
        "ollama"
    )
    if effective == "anthropic":
        # Same model for both roles: one client, so both share one rate limiter.
        if config.ANTHROPIC_TICK_MODEL == (model or config.ANTHROPIC_MODEL):
            return main, None
        return main, build_llm_client(provider="anthropic", ollama_url=ollama_url, model=config.ANTHROPIC_TICK_MODEL)
    if effective == "groq":
        return main, build_llm_client(provider="groq", ollama_url=ollama_url, model=config.GROQ_FAST_MODEL)
    return main, None
