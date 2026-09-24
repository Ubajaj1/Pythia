"""Jev coherence judge: is an agent's stated reasoning consistent with its actions?"""

from __future__ import annotations

from pythia.jev.core import Answer, JevAsker, NoulQ
from pythia.models import Agent

PIECE = "coherence"
JEV_INCOHERENT_FALLBACK_SUMMARY = "Stated reasoning did not match actions (flagged by Jev)."

# The same judging rules as evaluator.EVAL_PROMPT.
_INSTRUCTIONS = (
    "Is this agent's reasoning coherent across the history? Changing its mind or deviating from "
    "its archetype is fine. It is incoherent only if stated reasoning directly contradicts the action "
    "taken, reasoning contradicts itself within one tick, or a stance shift larger than 0.3 has empty "
    "or generic reasoning."
)


async def judge_coherence(agent: Agent, history: str, jev: JevAsker) -> Answer:
    state = {
        "agent": f"{agent.name} ({agent.role}), bias: {agent.bias}",
        "behavioral_rules": agent.behavioral_rules,
        "history": history,
    }
    q = NoulQ(_INSTRUCTIONS, true="Reasoning is consistent with actions",
              false="Reasoning contradicts actions or big shifts are unexplained")
    return (await jev.ask(state, {"coherent": q}))["coherent"]
