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


def _dedupe_agent_ids(agents: list[Agent]) -> list[Agent]:
    """Enforce unique agent IDs by appending a numeric suffix on collisions.

    The engine stores state in a dict keyed by `agent.id` (`current_stances`).
    Two agents with the same id silently overwrite each other's stance every
    tick, causing the aggregate to miscount and breaking the simulation. The
    LLM sometimes returns colliding IDs when multiple archetypes produce a
    similar slug (e.g. two "Marcus Chen" analysts both getting `analyst-marcus`).

    Strategy: keep the first occurrence of each id, suffix later duplicates
    with `-2`, `-3`, etc. and rewrite inbound relationship targets so the graph
    still resolves.
    """
    id_counts: dict[str, int] = {}
    for a in agents:
        id_counts[a.id] = id_counts.get(a.id, 0) + 1

    duplicate_ids = {aid for aid, c in id_counts.items() if c > 1}
    if not duplicate_ids:
        return agents

    logger.info(
        "Deduplicating %d duplicate agent id(s): %s",
        len(duplicate_ids), duplicate_ids,
    )

    # First pass: compute the remapping. We iterate in order so the first
    # occurrence keeps its id, the second becomes `<id>-2`, etc.
    seen: dict[str, int] = {}
    # Map from (original_id, occurrence_index) → new_id. The first occurrence
    # isn't rewritten; relationships pointing at the original id still resolve
    # to the first agent because that's what the LLM meant.
    new_ids: list[str] = []
    for a in agents:
        seen[a.id] = seen.get(a.id, 0) + 1
        if seen[a.id] == 1:
            new_ids.append(a.id)
        else:
            new_id = f"{a.id}-{seen[a.id]}"
            # Guard against the suffixed id already existing in the roster.
            existing = {x.id for x in agents}
            while new_id in existing or new_id in new_ids:
                seen[a.id] += 1
                new_id = f"{a.id}-{seen[a.id]}"
            new_ids.append(new_id)

    # Second pass: build updated agents with the new ids. Relationship targets
    # that pointed at a deduplicated id are intentionally left alone — they
    # will resolve to the first (canonical) agent with that id, which matches
    # the LLM's original intent.
    updated = []
    for a, new_id in zip(agents, new_ids):
        if new_id == a.id:
            updated.append(a)
        else:
            updated.append(a.model_copy(update={"id": new_id}))
    return updated


def _ensure_moderate_voice(
    agents: list[Agent],
    extreme_low: float = 0.3,
    extreme_high: float = 0.7,
    moderate_low: float = 0.4,
    moderate_high: float = 0.6,
) -> list[Agent]:
    """Nudge ONE agent's starting stance toward neutral when the panel is U-shaped.

    A U-shaped panel (agents clustered at both extremes, nobody in the middle)
    has two known failure modes:

    1. Echo chambers — each half reinforces its own side, the aggregate is a
       mean of two stalemated clusters and doesn't reflect real debate.
    2. Missing real-world stakeholders — most real decisions include at least
       one moderate voice (a fence-sitter, a data-driven pragmatist). The
       analyzer's archetype stance_ranges don't always guarantee one.

    Strategy: if ≥2 agents sit below `extreme_low` AND ≥2 agents sit above
    `extreme_high` AND NO agent sits in [moderate_low, moderate_high], pick
    the agent whose stance is closest to the middle and shift only that
    agent into the moderate band. Preserve everyone else exactly.

    This is much gentler than a panel-wide mean shift: it adds missing
    composition without overwriting the analyzer's intent for the clearly
    partisan voices.
    """
    if len(agents) < 3:
        return agents

    low_side = [a for a in agents if a.initial_stance < extreme_low]
    high_side = [a for a in agents if a.initial_stance > extreme_high]
    middle = [a for a in agents if moderate_low <= a.initial_stance <= moderate_high]

    if len(low_side) < 2 or len(high_side) < 2 or middle:
        # Not U-shaped, or already has a moderate — leave alone.
        return agents

    # Pick the agent closest to 0.5 to promote to a moderate. Tiebreak by
    # lower bias_strength (easier to move without fighting their bias).
    closest = min(
        agents,
        key=lambda a: (abs(a.initial_stance - 0.5), a.bias_strength),
    )
    # Place them at the nearer edge of the moderate band so we move the
    # minimum distance possible.
    if closest.initial_stance < 0.5:
        new_stance = moderate_low
    else:
        new_stance = moderate_high

    if abs(new_stance - closest.initial_stance) < 0.01:
        return agents

    logger.info(
        "Promoting agent=%s (stance %.2f) to moderate voice (stance %.2f) — "
        "panel was U-shaped with no middle-ground voice",
        closest.name, closest.initial_stance, new_stance,
    )

    updated = []
    for a in agents:
        if a.id == closest.id:
            updated.append(a.model_copy(update={"initial_stance": new_stance}))
        else:
            updated.append(a)
    return updated


# Biases that net-pull toward 1.0 (support end)
_PRO_LEANING_BIASES = frozenset({"optimism_bias"})
# Biases that net-pull toward 0.0 (oppose end)
_CON_LEANING_BIASES = frozenset({"negativity_bias"})


def _bias_imbalance(agents: list[Agent]) -> int:
    """Return (#pro-leaning biases) - (#con-leaning biases) weighted by strength.

    Returned as a rough int score: positive = panel leans pro mechanically,
    negative = panel leans con mechanically. Used only for logging so
    operators can see when the panel composition has a directional bias tilt.

    This is a diagnostic, not a corrector — we don't rewrite biases, because
    the analyzer picks them deliberately based on archetype.
    """
    score = 0.0
    for a in agents:
        if a.bias in _PRO_LEANING_BIASES:
            score += a.bias_strength
        elif a.bias in _CON_LEANING_BIASES:
            score -= a.bias_strength
    return round(score, 2)


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

    # Enforce unique agent IDs. The engine keys state by `agent.id`, so
    # colliding IDs silently drop agents from the aggregate. Suffix duplicates
    # with `-2`, `-3`, etc. so every agent has its own slot in `current_stances`.
    agents = _dedupe_agent_ids(agents)

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

    # Ensure at least one moderate voice when the panel is U-shaped. This adds
    # missing composition (a real-world panel usually has a fence-sitter) without
    # overwriting the analyzer's partisan archetypes. Much gentler than a
    # panel-wide mean shift, which we rejected because it makes per-tick
    # dynamics too sticky around 0.5.
    agents = _ensure_moderate_voice(agents)

    # Diagnostic: log bias directionality so operators can spot when a panel's
    # mechanical biases net-pull toward one extreme (e.g. 2x negativity, 0x
    # optimism means agents are being pulled toward 0 every tick).
    imbalance = _bias_imbalance(agents)
    if abs(imbalance) >= 0.5:
        logger.warning(
            "Bias directionality imbalance=%+.2f — panel has unequal mechanical pull "
            "toward %s end. Consider pairing optimism_bias with negativity_bias.",
            imbalance, "support" if imbalance > 0 else "oppose",
        )

    logger.info(
        "Generation complete total_agents=%d names=%s",
        len(agents), [a.name for a in agents],
    )
    return agents
