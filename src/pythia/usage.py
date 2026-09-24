"""Per-run token and cost accounting.

Clients call record_usage() after each response. A run opens a scope with
start_usage(); asyncio tasks created inside the run inherit the ContextVar,
so concurrent agent calls all land in the same RunUsage.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

# USD per 1M tokens (input, output). Claude prices from the Claude API reference
# (2026-09). Verify the non-Claude rows against provider pricing pages before release.
# A model missing from this table makes the run's cost unknown (None), never 0.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # TypeSafe Jev bills input tokens only; it returns typed answers, not text.
    "jev-latest": (0.042, 0.0),
}


@dataclass
class RunUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    by_model: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": None if self.cost_usd is None else round(self.cost_usd, 6),
            "by_model": self.by_model,
        }


_current: ContextVar[RunUsage | None] = ContextVar("pythia_run_usage", default=None)


def start_usage() -> tuple[RunUsage, Token]:
    usage = RunUsage()
    return usage, _current.set(usage)


def stop_usage(token: Token) -> None:
    try:
        _current.reset(token)
    except ValueError:
        # An async generator can be finalized in a different context than it started in.
        _current.set(None)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    usage = _current.get()
    if usage is None:
        return
    usage.calls += 1
    usage.input_tokens += input_tokens
    usage.output_tokens += output_tokens
    m = usage.by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    m["calls"] += 1
    m["input_tokens"] += input_tokens
    m["output_tokens"] += output_tokens
    price = PRICES_PER_MTOK.get(model)
    if price is None or usage.cost_usd is None:
        usage.cost_usd = None
    else:
        usage.cost_usd += (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
