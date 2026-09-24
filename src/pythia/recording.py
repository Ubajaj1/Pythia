"""LLM wrapper that reports every call to a session recorder and applies replay model overrides."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable, Protocol

from pythia.llm import LLMClient, build_llm_client, parse_model_spec

logger = logging.getLogger(__name__)

__all__ = [
    "NullRecorder", "RecordingLLMClient", "SessionRecorder",
    "client_for_model", "infer_provider", "parse_model_spec",
]


class SessionRecorder(Protocol):
    def record_llm_call(
        self, *, role: str, requested_model: str, model: str, provider: str,
        system: str | None, prompt: str, response: dict, latency_ms: int,
        started_at: datetime, ended_at: datetime,
    ) -> None: ...

    def model_for(self, requested_model: str) -> str | None: ...


class NullRecorder:
    def record_llm_call(self, **_: object) -> None:
        return None

    def model_for(self, requested_model: str) -> str | None:
        return None


_PREFIX_PROVIDERS = (("gpt-", "openai"), ("o1", "openai"), ("o3", "openai"), ("claude-", "anthropic"), ("llama", "groq"), ("gemma", "groq"), ("mixtral", "groq"))


def infer_provider(model: str) -> tuple[str, str]:
    """Resolve a bare model name (or "provider:model") to (provider, model)."""
    if ":" in model:
        return parse_model_spec(model)
    for prefix, provider in _PREFIX_PROVIDERS:
        if model.startswith(prefix):
            return provider, model
    raise ValueError(f"Cannot infer provider for model {model!r}; use 'provider:model'")


def client_for_model(model: str) -> LLMClient:
    provider, name = infer_provider(model)
    return build_llm_client(provider=provider, model=name)


class RecordingLLMClient:
    """Implements LLMClient. Delegates to `inner`, or to an override client when the
    recorder maps the inner client's model to another model (Kitaru replay overrides)."""

    def __init__(
        self,
        inner: LLMClient,
        role: str,
        recorder: SessionRecorder,
        factory: Callable[[str], LLMClient] | None = None,
    ):
        self.inner = inner
        self.role = role
        self.recorder = recorder
        self._factory = factory or client_for_model
        self._override_model: str | None = None
        self._override_client: LLMClient | None = None

    @property
    def model(self) -> str:
        return getattr(self.inner, "model", "unknown")

    @property
    def provider_name(self) -> str:
        return getattr(self.inner, "provider_name", "unknown")

    def _target(self) -> LLMClient:
        mapped = self.recorder.model_for(self.model)
        if not mapped or mapped == self.model:
            return self.inner
        if mapped != self._override_model:
            logger.info("Replay override role=%s %s -> %s", self.role, self.model, mapped)
            self._override_client = self._factory(mapped)
            self._override_model = mapped
        return self._override_client  # type: ignore[return-value]

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        target = self._target()
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        response = await target.generate(prompt=prompt, system=system, seed=seed)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        self.recorder.record_llm_call(
            role=self.role,
            requested_model=self.model,
            model=getattr(target, "model", "unknown"),
            provider=getattr(target, "provider_name", "unknown"),
            system=system,
            prompt=prompt,
            response=response,
            latency_ms=latency_ms,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
        )
        return response

    async def close(self) -> None:
        for client in (self.inner, self._override_client):
            close = getattr(client, "close", None)
            if close:
                await close()
