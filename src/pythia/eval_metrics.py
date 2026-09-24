"""Deterministic metrics over a finished run. No LLM calls."""

from __future__ import annotations

from typing import Literal

from pythia.models import RunResult

# Must match the fallback reasoning string in SimulationEngine._run_agent_tick.
PARSE_FAILURE_REASONING = "Failed to parse response"


def _events(result: RunResult):
    for tick in result.ticks:
        yield from tick.events


def parse_failure_rate(result: RunResult) -> float:
    events = list(_events(result))
    if not events:
        return 0.0
    failed = sum(1 for e in events if e.reasoning == PARSE_FAILURE_REASONING)
    return failed / len(events)


def target_validity_rate(result: RunResult) -> float:
    agent_ids = {a.id for a in result.agents}
    targeted = [e for e in _events(result) if e.influence_target]
    if not targeted:
        return 1.0
    return sum(1 for e in targeted if e.influence_target in agent_ids) / len(targeted)


def stance_volatility(result: RunResult) -> float:
    events = list(_events(result))
    if not events:
        return 0.0
    return sum(abs(e.stance - e.previous_stance) for e in events) / len(events)


def verdict_direction(stance: float, neutral_band: float = 0.1) -> Literal["buy", "sell", "neutral"]:
    if stance > 0.5 + neutral_band:
        return "buy"
    if stance < 0.5 - neutral_band:
        return "sell"
    return "neutral"


def run_metrics(result: RunResult) -> dict[str, float | str]:
    final = result.summary.final_aggregate_stance
    return {
        "parse_failure_rate": parse_failure_rate(result),
        "target_validity_rate": target_validity_rate(result),
        "stance_volatility": stance_volatility(result),
        "final_aggregate": final,
        "direction": verdict_direction(final),
    }
