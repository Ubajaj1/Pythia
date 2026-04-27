"""Decision Summary — translates simulation results into actionable human-readable insights."""

from __future__ import annotations

import logging

from pythia.llm import LLMClient
from pythia.models import (
    DecisionSummary,
    InfluenceGraph,
    KeyArgument,
    RunResult,
)

logger = logging.getLogger(__name__)

DECISION_SYSTEM = """\
You are Pythia's Decision Interpreter. Given a completed simulation with agent trajectories
and influence data, produce a human-readable decision summary.

You are NOT making the decision for the user. You are translating what the simulation revealed
into clear, actionable language so the user can make an informed choice.

Your output MUST be a JSON object with:
- verdict: string — one sentence describing where the panel landed (e.g. "The panel leans toward raising a Series A, but with significant reservations about timing")
- confidence: string — one of "high", "moderate", "low", "polarized"
- confidence_rationale: string — one sentence explaining why (e.g. "4 of 5 agents converged, but the dissenter raised an unaddressed risk")
- arguments_for: array of objects with agent_name, agent_role, position, reasoning — the 2-3 strongest arguments toward the high end of the stance spectrum
- arguments_against: array of objects with agent_name, agent_role, position, reasoning — the 2-3 strongest arguments toward the low end
- key_risk: string — the single most important risk or blind spot the simulation revealed
- what_could_change: string — conditions under which the minority position would become the majority
- influence_narrative: string — 2-3 sentences describing the key influence dynamics (who moved whom and why)
- herd_moments: array of strings — 0-3 moments where group dynamics dominated individual reasoning"""


def _build_decision_prompt(result: RunResult, graph: InfluenceGraph) -> str:
    """Build the prompt for the decision summary LLM call."""
    lines = [
        f"User's question: {result.scenario.input}",
        f"Scenario: {result.scenario.title}",
        f"Stance spectrum: {result.scenario.stance_spectrum}",
        f"  (0.0 = {result.scenario.stance_spectrum[0]}, 1.0 = {result.scenario.stance_spectrum[-1]})",
        "",
        "Agent final positions:",
    ]

    # Build agent trajectories
    agent_initial = {a.id: a for a in result.agents}
    agent_final_stances: dict[str, float] = {}
    agent_final_reasoning: dict[str, str] = {}
    for tick in result.ticks:
        for event in tick.events:
            agent_final_stances[event.agent_id] = event.stance
            agent_final_reasoning[event.agent_id] = event.reasoning

    for agent in result.agents:
        final = agent_final_stances.get(agent.id, agent.initial_stance)
        reasoning = agent_final_reasoning.get(agent.id, "")
        direction = "↑" if final > agent.initial_stance else "↓" if final < agent.initial_stance else "→"
        lines.append(
            f"  {agent.name} ({agent.role}, bias: {agent.bias}): "
            f"{agent.initial_stance:.2f} → {final:.2f} {direction}  "
            f'reasoning: "{reasoning}"'
        )

    lines.append(f"\nFinal aggregate stance: {result.summary.final_aggregate_stance:.2f}")
    lines.append(f"Consensus reached: {result.summary.consensus_reached}")

    # Add influence chain highlights
    top_influences = graph.get_strongest_influence_chains(top_n=5)
    if top_influences:
        lines.append("\nKey influence events:")
        for edge in top_influences:
            source_name = agent_initial.get(edge.source_id)
            target_name = agent_initial.get(edge.target_id)
            s_name = source_name.name if source_name else edge.source_id
            t_name = target_name.name if target_name else edge.target_id
            lines.append(
                f"  Tick {edge.tick}: {s_name} → {t_name} "
                f'(delta: {edge.influence_delta:+.2f}) "{edge.message[:80]}"'
            )

    # Add herd moments
    herd_ticks = graph.get_herd_moments(len(result.agents))
    if herd_ticks:
        lines.append(f"\nHerd behavior detected at ticks: {herd_ticks}")

    return "\n".join(lines)


async def generate_decision_summary(
    result: RunResult,
    graph: InfluenceGraph,
    llm: LLMClient,
) -> DecisionSummary:
    """Generate a human-readable decision summary from simulation results. One LLM call."""
    logger.info("Generating decision summary for run_id=%s", result.run_id)

    prompt = _build_decision_prompt(result, graph)
    logger.debug("Decision summary prompt:\n%s", prompt)

    raw = await llm.generate(prompt=prompt, system=DECISION_SYSTEM)

    # Parse arguments
    def _parse_args(raw_args: list) -> list[KeyArgument]:
        args = []
        for a in raw_args:
            if isinstance(a, dict):
                args.append(KeyArgument(
                    agent_name=str(a.get("agent_name", "")),
                    agent_role=str(a.get("agent_role", "")),
                    position=str(a.get("position", "")),
                    reasoning=str(a.get("reasoning", "")),
                ))
        return args

    # Parse herd moments
    herd_moments = []
    for m in raw.get("herd_moments", []):
        if isinstance(m, str):
            herd_moments.append(m)

    summary = DecisionSummary(
        verdict=str(raw.get("verdict", "The simulation did not reach a clear conclusion.")),
        verdict_stance=result.summary.final_aggregate_stance,
        confidence=str(raw.get("confidence", "low")),
        confidence_rationale=str(raw.get("confidence_rationale", "")),
        arguments_for=_parse_args(raw.get("arguments_for", [])),
        arguments_against=_parse_args(raw.get("arguments_against", [])),
        key_risk=str(raw.get("key_risk", "")),
        what_could_change=str(raw.get("what_could_change", "")),
        influence_narrative=str(raw.get("influence_narrative", "")),
        herd_moments=herd_moments,
    )

    logger.info(
        "Decision summary generated verdict=%r confidence=%s",
        summary.verdict[:60], summary.confidence,
    )
    return summary
