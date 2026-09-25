"""Jev behaviour settings: bias, bias strength, initial stance, relationships.

The LLM still writes each agent's persona and behavioural rules; Jev judges the
numeric and categorical settings from those personas.
"""

from __future__ import annotations

import logging

from pythia.biases import BIAS_CATALOG
from pythia.jev.core import Answer, ChoiceQ, JevAsker, ScoreQ, get_jev, jev_mode, record_shadow, threshold
from pythia.jev.mapping import (
    RELATION_OPTIONS, STRENGTH_LEVELS, clamp, ordinal_agree, prune_relationships,
    stance_from_score, strength_from_score,
)
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint

logger = logging.getLogger(__name__)
PIECE = "behaviour"


def _archetype_for(agent: Agent, blueprint: ScenarioBlueprint) -> AgentArchetype | None:
    return next((arch for arch in blueprint.agent_archetypes if arch.role == (agent.archetype or agent.role)), None)


def _state(agents: list[Agent], blueprint: ScenarioBlueprint) -> dict:
    """What Jev sees: the same scenario and archetype context the LLM generated each agent from.

    Behavioural rules and the LLM's settings are left out: the rules were written from the
    LLM's own bias pick, so including them would hand Jev the answer it is being compared on.
    """
    cast = []
    for a in agents:
        entry = {"id": a.id, "name": a.name, "role": a.role, "persona": a.persona}
        arch = _archetype_for(a, blueprint)
        if arch is not None:
            entry["archetype"] = {
                "name": arch.role,
                "description": arch.description,
                "suggested_biases": arch.suggested_biases or [arch.bias],
            }
        cast.append(entry)
    return {
        "scenario": f"{blueprint.title}. {blueprint.description}",
        "dynamics": blueprint.dynamics,
        "stance_spectrum_low_to_high": blueprint.stance_spectrum,
        "cast": cast,
    }


def _agent_questions(agents: list[Agent], blueprint: ScenarioBlueprint) -> dict:
    bias_options = {cid: f"{e.name}: {e.layman}" for cid, e in BIAS_CATALOG.items()}
    qs = {}
    for a in agents:
        who = f"{a.name} (id {a.id})"
        qs[f"{a.id}:bias"] = ChoiceQ(
            f"Which cognitive bias best fits {who}, given their persona and archetype? The archetype's "
            "suggested biases are a starting point, and agents sharing an archetype usually differ.",
            bias_options,
        )
        qs[f"{a.id}:strength"] = ScoreQ(f"How strongly does that bias shape {who}'s thinking?", STRENGTH_LEVELS)
        qs[f"{a.id}:stance"] = ScoreQ(f"Before any discussion, where does {who} stand on the scenario?", blueprint.stance_spectrum)
    return qs


def _relation_questions(agents: list[Agent]) -> dict:
    return {
        f"rel:{a.id}->{b.id}": ChoiceQ(f"How does {a.name} relate to {b.name}?", RELATION_OPTIONS)
        for a in agents for b in agents if a.id != b.id
    }


def _range_for(agent: Agent, blueprint: ScenarioBlueprint) -> tuple[float, float]:
    arch = _archetype_for(agent, blueprint)
    return arch.stance_range if arch is not None else (0.0, 1.0)


async def apply_behaviour_judgement(
    agents: list[Agent], blueprint: ScenarioBlueprint,
    jev: JevAsker | None = None, mode: str | None = None,
) -> list[Agent]:
    """Record (shadow) or apply (primary) Jev's behaviour settings; LLM values stay on any doubt."""
    mode = mode or jev_mode(PIECE)
    if mode == "off":
        return agents
    jev = jev or get_jev()
    if jev is None:
        return agents
    try:
        state = _state(agents, blueprint)
        # Two requests keep each under Jev's state+question token budget.
        answers = await jev.ask(state, _agent_questions(agents, blueprint))
        answers |= await jev.ask(state, _relation_questions(agents))
    except Exception:
        logger.exception("Jev behaviour judgement failed; keeping LLM values")
        return agents

    primary, cut, n = mode == "primary", threshold(), len(blueprint.stance_spectrum)
    rel_pairs: dict[tuple[str, str], Answer] = {
        tuple(k[4:].split("->")): v for k, v in answers.items() if k.startswith("rel:")
    }
    jev_rels = prune_relationships(rel_pairs)
    out = []
    for a in agents:
        upd: dict = {}
        bias = answers[f"{a.id}:bias"]
        use = primary and bias.confidence >= cut
        record_shadow(PIECE, f"{a.id}:bias", a.bias, bias.value, bias.confidence, bias.value == a.bias, "jev" if use else "llm")
        if use:
            upd["bias"] = str(bias.value)

        strength = answers[f"{a.id}:strength"]
        s_val = round(strength_from_score(float(strength.value)), 4)
        use = primary and strength.confidence >= cut
        record_shadow(PIECE, f"{a.id}:strength", a.bias_strength, s_val, strength.confidence,
                      abs(s_val - a.bias_strength) <= 0.2, "jev" if use else "llm")
        if use:
            upd["bias_strength"] = s_val

        stance = answers[f"{a.id}:stance"]
        lo, hi = _range_for(a, blueprint)
        st_val = round(clamp(stance_from_score(float(stance.value), n), lo, hi), 4)
        use = primary and stance.confidence >= cut
        record_shadow(PIECE, f"{a.id}:stance", a.initial_stance, st_val, stance.confidence,
                      ordinal_agree(st_val, a.initial_stance, n), "jev" if use else "llm")
        if use:
            upd["initial_stance"] = st_val

        # Relationships are recorded per ordered pair, but applied as a set: Jev's replace
        # the LLM's only when every pair answer for this agent (including "none") clears the threshold.
        llm_rel = {r.target: r.type for r in a.relationships}
        my_pairs = {tgt: ans for (src, tgt), ans in rel_pairs.items() if src == a.id}
        use = primary and bool(my_pairs) and min(ans.confidence for ans in my_pairs.values()) >= cut
        for tgt, ans in my_pairs.items():
            llm_type = llm_rel.get(tgt, "none")
            record_shadow(PIECE, f"{a.id}->{tgt}:relationship", llm_type, ans.value, ans.confidence,
                          ans.value == llm_type, "jev" if use else "llm")
        if use:
            upd["relationships"] = [Relationship(target=t, type=ty, weight=w) for t, ty, w in jev_rels.get(a.id, [])]
        out.append(a.model_copy(update=upd) if upd else a)
    return out
