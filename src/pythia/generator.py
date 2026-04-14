"""Agent Generator — creates fully realized agents from a scenario blueprint."""

from __future__ import annotations

import asyncio
import json

from pythia.llm import LLMClient
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint

PASS1_SYSTEM = """\
You are Pythia's Agent Generator. Given a scenario and an agent archetype, generate unique agents as JSON.

Your output MUST be a JSON object with an "agents" key containing an array. Each agent has:
- id: string — lowercase-hyphenated (e.g. "retail-rachel")
- name: string — a memorable character name
- role: string — matches the archetype role
- persona: string — 1-2 sentences describing personality, background, motivations (~50 words max)
- bias: string — the cognitive bias from the archetype
- initial_stance: float — between {stance_low} and {stance_high}
- behavioral_rules: array of 2-4 short strings describing how this agent behaves

Make each agent distinct and memorable. Give them human-like personalities."""

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
        f"Bias: {archetype.bias}\n"
        f"Stance range: {archetype.stance_range[0]} to {archetype.stance_range[1]}\n"
        f"Count: {archetype.count}\n\n"
        f"Generate {archetype.count} agent(s)."
    )
    raw = await llm.generate(prompt=prompt, system=system)
    agents_data = raw.get("agents", [])
    return [
        Agent(
            id=a["id"],
            name=a["name"],
            role=a["role"],
            persona=a["persona"],
            bias=a["bias"],
            initial_stance=a["initial_stance"],
            behavioral_rules=a["behavioral_rules"],
            relationships=[],
        )
        for a in agents_data
    ]


async def _assign_relationships(
    agents: list[Agent],
    llm: LLMClient,
) -> list[Agent]:
    """Pass 2: Assign relationships given the full cast."""
    agent_summaries = [
        f"- {a.id} ({a.name}): {a.role}, bias={a.bias}, stance={a.initial_stance}, persona: {a.persona}"
        for a in agents
    ]
    prompt = "Agents in this simulation:\n" + "\n".join(agent_summaries)
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
    return updated


def _check_diversity(agents: list[Agent], min_spread: float = 0.6) -> bool:
    """Check that initial stances span at least min_spread of the 0.0-1.0 range."""
    if len(agents) < 2:
        return True
    stances = [a.initial_stance for a in agents]
    return (max(stances) - min(stances)) >= min_spread


async def generate_agents(
    blueprint: ScenarioBlueprint,
    llm: LLMClient,
) -> list[Agent]:
    """Generate agents from a blueprint. Two-pass: create agents, then assign relationships."""
    # Pass 1: parallel generation per archetype
    tasks = [
        _generate_for_archetype(arch, blueprint, llm)
        for arch in blueprint.agent_archetypes
    ]
    results = await asyncio.gather(*tasks)
    agents = [agent for group in results for agent in group]

    # Diversity check: if stances are too clustered, regenerate the most extreme archetype
    if not _check_diversity(agents) and len(blueprint.agent_archetypes) > 1:
        stances = {a.id: a.initial_stance for a in agents}
        mean = sum(stances.values()) / len(stances)
        archetype_dists = []
        for i, arch in enumerate(blueprint.agent_archetypes):
            arch_agents = [a for a in agents if a.role == arch.role]
            avg_dist = sum(abs(a.initial_stance - mean) for a in arch_agents) / max(len(arch_agents), 1)
            archetype_dists.append((i, avg_dist))
        archetype_dists.sort(key=lambda x: x[1])
        regen_idx = archetype_dists[0][0]
        regen_arch = blueprint.agent_archetypes[regen_idx]
        new_agents = await _generate_for_archetype(regen_arch, blueprint, llm)
        agents = [a for a in agents if a.role != regen_arch.role] + new_agents

    # Pass 2: assign relationships
    agents = await _assign_relationships(agents, llm)

    return agents
