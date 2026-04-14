"""LLM client abstraction — stub. Full implementation in Task 3."""

from typing import Protocol


class LLMClient(Protocol):
    """Protocol for LLM backends."""

    async def generate(self, prompt: str, system: str | None = None) -> dict: ...
