"""Evaluator — grades each agent's reasoning coherence after a simulation run."""

from __future__ import annotations

import asyncio

from pythia.llm import LLMClient
from pythia.models import Agent, AgentEvaluation, RunResult, TickEvent


EVAL_SYSTEM = """\
You are evaluating whether an AI agent's reasoning is internally coherent.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON."""


EVAL_PROMPT = """\
Agent: {name} ({role})
Cognitive bias: {bias}

Behavioral rules:
{rules}

Agent's tick-by-tick history in this simulation:
{history}

Question: Was this agent's reasoning coherent?

Rules for judging:
- It is FINE for the agent to deviate from their archetype — people surprise us.
- It is FINE for the agent to change their mind across ticks.
- Flag as INCOHERENT only if:
  (a) The stated reasoning directly contradicts the action taken
  (b) The reasoning is self-contradictory within a single tick
  (c) There is NO reasoning given for a large stance shift (change > 0.3 with empty or generic reasoning)

Respond with ONLY this JSON:
{{"is_coherent": true, "incoherence_summary": null}}
or
{{"is_coherent": false, "incoherence_summary": "<one sentence describing what was incoherent>"}}"""


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


def extract_agent_tick_pairs(
    run_result: RunResult, agent_id: str
) -> list[tuple[int, TickEvent]]:
    """Return [(tick_num, TickEvent)] for one agent across all ticks."""
    pairs = []
    for tick_record in run_result.ticks:
        for event in tick_record.events:
            if event.agent_id == agent_id:
                pairs.append((tick_record.tick, event))
    return pairs


async def evaluate_agent(
    agent: Agent,
    tick_pairs: list[tuple[int, TickEvent]],
    llm: LLMClient,
) -> AgentEvaluation:
    """Evaluate one agent's reasoning coherence. One LLM call."""
    prompt = EVAL_PROMPT.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        rules=_format_rules(agent.behavioral_rules),
        history=_format_history(tick_pairs),
    )
    raw = await llm.generate(prompt=prompt, system=EVAL_SYSTEM)
    return AgentEvaluation(
        agent_id=agent.id,
        is_coherent=bool(raw.get("is_coherent", True)),
        incoherence_summary=raw.get("incoherence_summary"),
    )


async def evaluate_run(
    run_result: RunResult,
    agents: list[Agent],
    llm: LLMClient,
) -> list[AgentEvaluation]:
    """Evaluate all agents in parallel. Returns one AgentEvaluation per agent."""
    tasks = [
        evaluate_agent(
            agent,
            extract_agent_tick_pairs(run_result, agent.id),
            llm,
        )
        for agent in agents
    ]
    return list(await asyncio.gather(*tasks))
