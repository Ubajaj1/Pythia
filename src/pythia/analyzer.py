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
- tick_count: integer (default 20)

Generate 3-5 archetypes with diverse stance_ranges that span the spectrum. Total agent count should be 5-10."""


async def analyze_scenario(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
) -> ScenarioBlueprint:
    """Analyze a user prompt and return a simulation blueprint."""
    logger.info("Analyzing scenario prompt=%r", prompt[:80] + ("..." if len(prompt) > 80 else ""))
    if context:
        logger.info("Context provided context_chars=%d", len(context))

    user_prompt = f"User's decision/question: {prompt}"
    if context:
        user_prompt += f"\n\nAdditional context: {context}"

    logger.debug("Analyzer full prompt:\n%s", user_prompt)

    raw = await llm.generate(prompt=user_prompt, system=SYSTEM_PROMPT)
    blueprint = ScenarioBlueprint.model_validate(raw)

    archetype_summary = ", ".join(
        f"{a.role}×{a.count}" for a in blueprint.agent_archetypes
    )
    logger.info(
        "Blueprint ready type=%s title=%r archetypes=[%s] ticks=%d",
        blueprint.scenario_type, blueprint.title, archetype_summary, blueprint.tick_count,
    )
    return blueprint
