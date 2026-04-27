"""Backward compatibility — re-exports OpenAICompatClient as OpenAIClient."""

from pythia.openai_compat_client import OpenAICompatClient as OpenAIClient  # noqa: F401

__all__ = ["OpenAIClient"]
