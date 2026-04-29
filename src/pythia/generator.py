"""Agent Generator — creates fully realized agents from a scenario blueprint."""

from __future__ import annotations

import asyncio
import json
import logging

from pythia.biases import BIAS_CATALOG, resolve_bias
from pythia.llm import LLMClient
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint

logger = logging.getLogger(__name__)

PASS1_SYSTEM = """\
You are Pythia's Agent Generator. Given a scenario and an agent archetype, generate unique agents as JSON.

Your output MUST be a JSON object with an "agents" key containing an array. Each agent has:
- id: string — lowercase-hyphenated (e.g. "retail-rachel")
- name: string — a memorable character name
- role: string — matches the archetype role
- persona: string — 1-2 sentences describing personality, background, motivations (~50 words max)
- bias: string — a cognitive bias from the suggested list (each agent in the same archetype should ideally have a DIFFERENT bias to avoid echo chambers)
- bias_strength: float — 0.0 to 1.0, how strongly this bias shapes their thinking (0.3 = mild, 0.5 = moderate, 0.8 = strong). Base this on persona cues — a rigid, set-in-their-ways character should have high strength; an open-minded one should have low strength.
- initial_stance: float — between {stance_low} and {stance_high}
- behavioral_rules: array of 2-4 short strings describing how this agent behaves

Make each agent distinct and memorable. Give them human-like personalities.
When generating multiple agents for the same archetype, vary their biases and strengths to avoid echo chambers."""

PASS2_SYSTEM = """\
You are assigning relationships between simulation agents. Given all agents, create a relationship graph.

Your output MUST be a JSON object with a "relationships" key. The value is an object where each key is an agent ID, and the value is an array of relationships:
- target: string — another agent's ID
- type: string — one of: "follows", "distrusts", "rivals", "respects"
- weight: float — 0.0 to 1.0 (how strong the relationship is)

Each agent should have 1-3 relationships. Relationships should make sense given their roles and personas."""


async def _generate_for_archetype(
    archetype: AgentArchetype,
    blueprint: ScenarioBlueprint,
    llm: LLMClient,
) -> list[Agent]:
    """Pass 1: Generate agents for one archetype."""
    logger.info(
        "Generating archetype role=%s count=%d bias=%s stance_range=[%.2f, %.2f]",
        archetype.role, archetype.count, archetype.bias,
        archetype.stance_range[0], archetype.stance_range[1],
    )
    system = PASS1_SYSTEM.format(
        stance_low=archetype.stance_range[0],
        stance_high=archetype.stance_range[1],
    )
    prompt = (
        f"Scenario: {blueprint.title} — {blueprint.description}\n"
        f"Dynamics: {blueprint.dynamics}\n"
        f"Stance spectrum: {json.dumps(blueprint.stance_spectrum)}\n\n"
        f"Archetype: {archetype.role}\n"
        f"Description: {archetype.description}\n"
        f"Primary bias: {archetype.bias}\n"
        f"Suggested biases (pick one per agent, vary across agents): "
        f"{json.dumps(archetype.suggested_biases) if archetype.suggested_biases else json.dumps([archetype.bias])}\n"
        f"Stance range: {archetype.stance_range[0]} to {archetype.stance_range[1]}\n"
        f"Count: {archetype.count}\n\n"
        f"Generate {archetype.count} agent(s). If generating multiple agents, give each a DIFFERENT bias from the suggested list."
    )
    logger.debug("Generator pass1 prompt archetype=%s:\n%s", archetype.role, prompt)

    raw = await llm.generate(prompt=prompt, system=system)
    agents_data = raw.get("agents", [])
    agents = []
    for a in agents_data:
        # Resolve bias through the catalog — never let a freeform string through
        raw_bias = a.get("bias", archetype.bias)
        canonical_bias = resolve_bias(raw_bias)
        if canonical_bias != raw_bias:
            logger.info(
                "Resolved agent bias %r → %s for agent %s",
                raw_bias, canonical_bias, a.get("name", "?"),
            )
        # Clamp bias_strength to [0.0, 1.0], default 0.5
        raw_strength = a.get("bias_strength", 0.5)
        try:
            strength = max(0.0, min(1.0, float(raw_strength)))
        except (TypeError, ValueError):
            strength = 0.5
        agents.append(Agent(
            id=a["id"],
            name=a["name"],
            role=a["role"],
            persona=a["persona"],
            bias=canonical_bias,
            bias_strength=strength,
            initial_stance=a["initial_stance"],
            behavioral_rules=a["behavioral_rules"],
            relationships=[],
        ))
    logger.info(
        "Archetype generated role=%s agents=%s stances=%s",
        archetype.role,
        [a.name for a in agents],
        [f"{a.initial_stance:.2f}" for a in agents],
    )
    return agents


async def _assign_relationships(
    agents: list[Agent],
    llm: LLMClient,
) -> list[Agent]:
    """Pass 2: Assign relationships given the full cast."""
    logger.info("Assigning relationships agents=%d", len(agents))
    agent_summaries = [
        f"- {a.id} ({a.name}): {a.role}, bias={a.bias}, stance={a.initial_stance}, persona: {a.persona}"
        for a in agents
    ]
    prompt = "Agents in this simulation:\n" + "\n".join(agent_summaries)
    logger.debug("Generator pass2 prompt:\n%s", prompt)

    raw = await llm.generate(prompt=prompt, system=PASS2_SYSTEM)

    relationships_map = raw.get("relationships", {})
    agent_ids = {a.id for a in agents}

    updated = []
    for agent in agents:
        rels_data = relationships_map.get(agent.id, [])
        rels = [
            Relationship(target=r["target"], type=r["type"], weight=r["weight"])
            for r in rels_data
            if r.get("target") in agent_ids and r["target"] != agent.id
        ]
        updated.append(agent.model_copy(update={"relationships": rels}))

    total_rels = sum(len(a.relationships) for a in updated)
    logger.info("Relationships assigned total=%d", total_rels)
    for a in updated:
        if a.relationships:
            rel_summary = ", ".join(f"{r.type}→{r.target}({r.weight:.1f})" for r in a.relationships)
            logger.debug("  %s relationships: %s", a.name, rel_summary)
    return updated


def _check_diversity(agents: list[Agent], min_spread: float = 0.6) -> bool:
    """Check that initial stances span at least min_spread of the 0.0-1.0 range."""
    if len(agents) < 2:
        return True
    stances = [a.initial_stance for a in agents]
    return (max(stances) - min(stances)) >= min_spread


def _dedupe_agent_names(agents: list[Agent]) -> list[Agent]:
    """Suffix duplicate agent names with their role.

    Two agents with the same name (e.g. two 'Alex Chen' across archetypes) break
    _resolve_influence_target's name-based fuzzy matching — any reference is
    ambiguous. Suffixing with the role keeps names human-readable while making
    them unique.
    """
    name_counts: dict[str, int] = {}
    for a in agents:
        name_counts[a.name] = name_counts.get(a.name, 0) + 1

    duplicates = {n for n, c in name_counts.items() if c > 1}
    if not duplicates:
        return agents

    logger.info("Deduplicating %d duplicate agent name(s): %s", len(duplicates), duplicates)
    updated = []
    for a in agents:
        if a.name in duplicates:
            new_name = f"{a.name} ({a.role.title()})"
            updated.append(a.model_copy(update={"name": new_name}))
        else:
            updated.append(a)
    return updated


async def generate_agents(
    blueprint: ScenarioBlueprint,
    llm: LLMClient,
) -> list[Agent]:
    """Generate agents from a blueprint. Two-pass: create agents, then assign relationships."""
    logger.info("Generation started archetypes=%d", len(blueprint.agent_archetypes))

    # Pass 1: parallel generation per archetype
    tasks = [
        _generate_for_archetype(arch, blueprint, llm)
        for arch in blueprint.agent_archetypes
    ]
    results = await asyncio.gather(*tasks)
    agents = [agent for group in results for agent in group]

    # Deduplicate agent names across archetypes.
    # Two agents with identical names (e.g. "Alex Chen" as founder AND investor)
    # break name-based fuzzy matching in _resolve_influence_target. Suffix
    # duplicates with their role so every name is unique.
    agents = _dedupe_agent_names(agents)

    # Diversity check: if stances are too clustered, regenerate the most extreme archetype
    if not _check_diversity(agents) and len(blueprint.agent_archetypes) > 1:
        stances = [a.initial_stance for a in agents]
        spread = max(stances) - min(stances)
        logger.warning(
            "Stance diversity check failed spread=%.2f min_required=0.60 — regenerating archetype",
            spread,
        )
        mean = sum(stances) / len(stances)
        archetype_dists = []
        for i, arch in enumerate(blueprint.agent_archetypes):
            arch_agents = [a for a in agents if a.role == arch.role]
            avg_dist = sum(abs(a.initial_stance - mean) for a in arch_agents) / max(len(arch_agents), 1)
            archetype_dists.append((i, avg_dist))
        archetype_dists.sort(key=lambda x: x[1])
        regen_idx = archetype_dists[0][0]
        regen_arch = blueprint.agent_archetypes[regen_idx]
        logger.info("Regenerating archetype role=%s", regen_arch.role)
        new_agents = await _generate_for_archetype(regen_arch, blueprint, llm)
        agents = [a for a in agents if a.role != regen_arch.role] + new_agents

    # Pass 2: assign relationships
    agents = await _assign_relationships(agents, llm)

    logger.info(
        "Generation complete total_agents=%d names=%s",
        len(agents), [a.name for a in agents],
    )
    return agents
