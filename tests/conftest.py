"""Shared test fixtures for Pythia tests."""

import json
from pythia.llm import LLMClient


class FakeLLMClient(LLMClient):
    """LLM client that returns canned responses for testing."""

    def __init__(self, responses: list[dict] | None = None):
        self.responses = list(responses) if responses else []
        self.calls: list[dict] = []

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        self.calls.append({"prompt": prompt, "system": system})
        if self.responses:
            return self.responses.pop(0)
        return {}
