"""Scenario Analyzer — classifies user input into a simulation blueprint."""

from __future__ import annotations

import logging

from pythia.llm import LLMClient
from pythia.models import ScenarioBlueprint

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Pythia's Scenario Analyzer. Given a user's decision or question, you produce a simulation blueprint as JSON.

Your output MUST be a JSON object with these exact fields:
- scenario_type: string (e.g. "market_event", "personal_decision", "policy_test")
- title: string — short descriptive title
- description: string — one sentence describing the simulation
- stance_spectrum: array of exactly 5 strings — labels for positions from 0.0 to 1.0, appropriate to the scenario (e.g. ["very bearish", "bearish", "neutral", "bullish", "very bullish"] for markets, ["strongly oppose", "oppose", "neutral", "support", "strongly support"] for policy)
- agent_archetypes: array of objects, each with:
    - role: string
    - count: integer (1-3)
    - description: string
    - bias: string (a cognitive bias name)
    - stance_range: [low, high] — floats between 0.0 and 1.0, low < high
- dynamics: string — describes how agents should interact
- tick_count: integer — number of simulation rounds

{agent_instruction}
{tick_instruction}

Generate archetypes with diverse stance_ranges that span the spectrum."""

# Auto mode: LLM picks counts based on scenario complexity
_AUTO_AGENT_INSTRUCTION = """\
Choose the right number of agents based on the scenario:
- Simple personal decisions (2 options, few stakeholders): 3-4 agents, 2-3 archetypes
- Business/strategy decisions (multiple stakeholders): 5-6 agents, 3-4 archetypes
- Complex policy/market scenarios (many factions): 7-8 agents, 4-5 archetypes
Pick the smallest number that covers the key perspectives. More agents is NOT better."""

_AUTO_TICK_INSTRUCTION = """\
Choose tick_count based on how much deliberation the scenario needs:
- Quick consensus likely (clear tradeoffs): 8-10 ticks
- Moderate debate expected (competing interests): 12-15 ticks
- Deep polarization likely (entrenched positions): 18-20 ticks"""

# Presets
_PRESETS = {
    "fast":     {"agent_count": 4,  "tick_count": 8},
    "balanced": {"agent_count": 6,  "tick_count": 15},
    "deep":     {"agent_count": 10, "tick_count": 25},
}


def _build_system_prompt(
    agent_count: int | None = None,
    tick_count: int | None = None,
) -> str:
    """Build the system prompt with user-specified, auto, or preset counts."""
    if agent_count:
        agent_instruction = (
            f"The user wants exactly {agent_count} total agents. "
            f"Distribute them across archetypes so the total count sums to {agent_count}."
        )
    else:
        agent_instruction = _AUTO_AGENT_INSTRUCTION

    if tick_count:
        tick_instruction = f"Set tick_count to exactly {tick_count}."
    else:
        tick_instruction = _AUTO_TICK_INSTRUCTION

    return SYSTEM_PROMPT.format(
        agent_instruction=agent_instruction,
        tick_instruction=tick_instruction,
    )


def resolve_preset(preset: str | None) -> dict:
    """Resolve a preset name to agent_count and tick_count. Returns empty dict if no preset."""
    if not preset or preset == "auto":
        return {}
    if preset in _PRESETS:
        return _PRESETS[preset]
    logger.warning("Unknown preset %r — falling back to auto", preset)
    return {}


async def analyze_scenario(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
) -> ScenarioBlueprint:
    """Analyze a user prompt and return a simulation blueprint.

    Args:
        agent_count: If set, instructs the LLM to generate this many agents total.
                     If None, the LLM picks based on scenario complexity (auto mode).
        tick_count: If set, overrides the tick count. If None, LLM picks (auto mode).
    """
    logger.info(
        "Analyzing scenario prompt=%r agent_count=%s tick_count=%s",
        prompt[:80] + ("..." if len(prompt) > 80 else ""),
        agent_count or "auto", tick_count or "auto",
    )
    if context:
        logger.info("Context provided context_chars=%d", len(context))

    user_prompt = f"User's decision/question: {prompt}"
    if context:
        user_prompt += f"\n\nAdditional context: {context}"

    logger.debug("Analyzer full prompt:\n%s", user_prompt)

    system = _build_system_prompt(agent_count=agent_count, tick_count=tick_count)
    raw = await llm.generate(prompt=user_prompt, system=system)
    blueprint = ScenarioBlueprint.model_validate(raw)

    # Override tick_count if user specified it (in case LLM didn't follow instructions)
    if tick_count and blueprint.tick_count != tick_count:
        logger.info("Overriding LLM tick_count %d → %d (user-specified)", blueprint.tick_count, tick_count)
        blueprint = blueprint.model_copy(update={"tick_count": tick_count})

    archetype_summary = ", ".join(
        f"{a.role}×{a.count}" for a in blueprint.agent_archetypes
    )
    total_agents = sum(a.count for a in blueprint.agent_archetypes)
    logger.info(
        "Blueprint ready type=%s title=%r archetypes=[%s] total_agents=%d ticks=%d",
        blueprint.scenario_type, blueprint.title, archetype_summary,
        total_agents, blueprint.tick_count,
    )
    return blueprint
