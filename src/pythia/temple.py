"""Temple of Learning — amends agent behavioral_rules additively after incoherence."""

from __future__ import annotations

from pythia.llm import LLMClient
from pythia.models import Agent, AgentEvaluation, TickEvent


TEMPLE_SYSTEM = """\
You are helping an AI simulation agent learn from its reasoning failures.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON."""


TEMPLE_PROMPT = """\
Agent: {name} ({role})
Cognitive bias: {bias}

Current behavioral rules:
{rules}

Why this agent's reasoning was flagged as incoherent:
{incoherence_summary}

Agent's action history in this run:
{history}

Task: Add 1-3 new behavioral rules that would prevent this incoherence in future runs.
Guidelines:
- DO NOT remove or restate existing rules.
- ADD rules that capture context-sensitive nuance or explain when the agent may deviate.
- The goal is richer, more honest reasoning — not forcing the agent to conform to its archetype.
- Example good rule: "When overriding loss-aversion instinct, explicitly state the triggering condition in reasoning."

Respond with ONLY this JSON:
{{"new_rules": ["rule 1", "rule 2"]}}"""


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def _format_history(tick_pairs: list[tuple[int, TickEvent]]) -> str:
    if not tick_pairs:
        return "(no history)"
    lines = []
    for tick_num, e in tick_pairs:
        delta = e.stance - e.previous_stance
        lines.append(
            f"Tick {tick_num}: stance {e.previous_stance:.2f}→{e.stance:.2f} ({delta:+.2f}), "
            f'action="{e.action}", reasoning="{e.reasoning}"'
        )
    return "\n".join(lines)


async def amend_agent(
    agent: Agent,
    evaluation: AgentEvaluation,
    tick_pairs: list[tuple[int, TickEvent]],
    llm: LLMClient,
) -> Agent:
    """Return agent with behavioral_rules augmented by amendment. Returns original if coherent."""
    if evaluation.is_coherent:
        return agent

    prompt = TEMPLE_PROMPT.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        rules=_format_rules(agent.behavioral_rules),
        incoherence_summary=evaluation.incoherence_summary or "Reasoning did not explain action",
        history=_format_history(tick_pairs),
    )
    raw = await llm.generate(prompt=prompt, system=TEMPLE_SYSTEM)
    new_rules = [r for r in raw.get("new_rules", []) if isinstance(r, str)]

    return agent.model_copy(update={
        "behavioral_rules": agent.behavioral_rules + new_rules,
    })
