"""Decision Summary — translates simulation results into actionable human-readable insights."""

from __future__ import annotations

import logging
import re

from pythia.confidence import ConfidenceReading, compute_confidence
from pythia.llm import LLMClient
from pythia.models import (
    DecisionSummary,
    InfluenceGraph,
    KeyArgument,
    RunResult,
)

logger = logging.getLogger(__name__)

# Step 7: citation pattern — matches [F1], [F23], etc.
_CITATION_PATTERN = re.compile(r"\[F\d+\]")

# Step 7: below this rate, an agent is flagged as "mostly ignored the document"
LOW_CITATION_THRESHOLD = 0.20

DECISION_SYSTEM = """\
You are Pythia's Decision Interpreter. Given a completed simulation with agent trajectories
and influence data, produce a human-readable decision summary.

You are NOT making the decision for the user. You are translating what the simulation revealed
into clear, actionable language so the user can make an informed choice.

CRITICAL: The user came here because they have a real decision to make. Generic summaries like
"the panel leans toward X" are useless. Be SPECIFIC about what the user should DO next.

IMPORTANT: The confidence label has already been computed deterministically from the panel's
final stance distribution and will be provided to you. Do NOT override it. Your job is to
write the CONFIDENCE_RATIONALE that explains WHY the panel landed at that confidence level —
referencing the specific agents, arguments, and dynamics that produced the dispersion you see.

Your output MUST be a JSON object with:
- verdict: string — one sentence describing where the panel landed AND what it means for the user's specific decision (e.g. "The panel favors raising a Series A now, primarily driven by competitive pressure — but the strongest dissent came from burn rate concerns that were never resolved")
- confidence_rationale: string — one sentence explaining WHY this confidence level emerged, citing specific agents or dynamics (e.g. "4 of 5 agents converged toward support, but the dissenter raised an unaddressed risk about burn rate that pulled the aggregate back")
- arguments_for: array of objects with agent_name, agent_role, position, reasoning — the 2-3 strongest arguments toward the high end of the stance spectrum
- arguments_against: array of objects with agent_name, agent_role, position, reasoning — the 2-3 strongest arguments toward the low end
- key_risk: string — the single most important risk or blind spot the simulation revealed. Be specific — name the risk, who raised it, and why it matters.
- what_could_change: string — specific conditions that would flip the outcome (e.g. "If burn rate were cut 30%, the conservative advisor would likely shift to support")
- actionable_takeaways: array of 2-4 strings — specific things the user should DO or INVESTIGATE before making this decision. Not vague advice. Examples: "Get a concrete burn rate projection for the next 18 months", "Talk to 2-3 founders who raised in similar market conditions", "Run the numbers on bootstrapped growth to 1M ARR as a comparison point"
- influence_narrative: string — 2-3 sentences describing the key influence dynamics (who moved whom and why, and what that reveals about the decision)
- herd_moments: array of strings — 0-3 moments where group dynamics dominated individual reasoning (these are WARNING signs — the group may have converged for social reasons, not logical ones)"""


def _build_decision_prompt(
    result: RunResult, graph: InfluenceGraph, reading: ConfidenceReading
) -> str:
    """Build the prompt for the decision summary LLM call."""
    lines = [
        f"User's question: {result.scenario.input}",
        f"Scenario: {result.scenario.title}",
        f"Stance spectrum: {result.scenario.stance_spectrum}",
        f"  (0.0 = {result.scenario.stance_spectrum[0]}, 1.0 = {result.scenario.stance_spectrum[-1]})",
        "",
        f"COMPUTED CONFIDENCE (deterministic, do NOT override): {reading.label}",
        f"  Agreement: {reading.agreement} (stance σ = {reading.stance_stddev:.2f})",
        f"  Conviction: {reading.conviction} (aggregate {reading.aggregate:.2f}, "
        f"distance from neutral {abs(reading.aggregate - 0.5):.2f})",
        f"  Stance spread (max − min): {reading.stance_spread:.2f}",
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


def _compute_grounded_reasoning_rates(result: RunResult) -> dict[str, float]:
    """Compute per-agent citation rate: fraction of tick events with at least one [Fxx] citation.

    Returns a dict of agent_id → rate (0.0 to 1.0). Only meaningful when grounding was used.
    """
    agent_total: dict[str, int] = {}
    agent_cited: dict[str, int] = {}

    for tick in result.ticks:
        for event in tick.events:
            agent_total[event.agent_id] = agent_total.get(event.agent_id, 0) + 1
            if _CITATION_PATTERN.search(event.reasoning):
                agent_cited[event.agent_id] = agent_cited.get(event.agent_id, 0) + 1

    rates = {}
    for agent_id, total in agent_total.items():
        cited = agent_cited.get(agent_id, 0)
        rates[agent_id] = round(cited / total, 4) if total > 0 else 0.0

    return rates


async def generate_decision_summary(
    result: RunResult,
    graph: InfluenceGraph,
    llm: LLMClient,
    has_grounding: bool = False,
) -> DecisionSummary:
    """Generate a human-readable decision summary from simulation results. One LLM call.

    Confidence is computed deterministically from final agent stances; the LLM
    only writes the rationale explaining why the dispersion looks the way it does.
    """
    logger.info("Generating decision summary for run_id=%s", result.run_id)

    # Compute deterministic confidence from the final tick's stances
    final_stances: list[float] = []
    if result.ticks:
        # For each agent, use its most recent stance across all ticks
        last_stances: dict[str, float] = {}
        for tick in result.ticks:
            for event in tick.events:
                last_stances[event.agent_id] = event.stance
        final_stances = list(last_stances.values())

    reading = compute_confidence(final_stances)
    logger.info(
        "Confidence reading label=%s agreement=%s conviction=%s σ=%.3f spread=%.3f",
        reading.label, reading.agreement, reading.conviction,
        reading.stance_stddev, reading.stance_spread,
    )

    prompt = _build_decision_prompt(result, graph, reading)
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

    # Parse actionable takeaways
    takeaways = []
    for t in raw.get("actionable_takeaways", []):
        if isinstance(t, str):
            takeaways.append(t)

    # Confidence label comes from the deterministic reading, NOT the LLM.
    # The LLM only provides the rationale.
    llm_rationale = str(raw.get("confidence_rationale", "")).strip()
    rationale = llm_rationale or reading.rationale

    # Step 7: compute per-agent grounded reasoning rates
    grounded_rates: dict[str, float] = {}
    if has_grounding and result.ticks:
        grounded_rates = _compute_grounded_reasoning_rates(result)
        for agent_id, rate in grounded_rates.items():
            if rate < LOW_CITATION_THRESHOLD:
                agent_name = next(
                    (a.name for a in result.agents if a.id == agent_id), agent_id
                )
                logger.info(
                    "Low grounding rate agent=%s rate=%.0f%% (threshold=%.0f%%)",
                    agent_name, rate * 100, LOW_CITATION_THRESHOLD * 100,
                )

    summary = DecisionSummary(
        verdict=str(raw.get("verdict", "The simulation did not reach a clear conclusion.")),
        verdict_stance=result.summary.final_aggregate_stance,
        confidence=reading.label,
        confidence_rationale=rationale,
        agreement_label=reading.agreement,
        conviction_label=reading.conviction,
        stance_stddev=reading.stance_stddev,
        stance_spread=reading.stance_spread,
        arguments_for=_parse_args(raw.get("arguments_for", [])),
        arguments_against=_parse_args(raw.get("arguments_against", [])),
        key_risk=str(raw.get("key_risk", "")),
        what_could_change=str(raw.get("what_could_change", "")),
        actionable_takeaways=takeaways,
        influence_narrative=str(raw.get("influence_narrative", "")),
        herd_moments=herd_moments,
        grounded_reasoning_rates=grounded_rates,
    )

    logger.info(
        "Decision summary generated verdict=%r confidence=%s",
        summary.verdict[:60], summary.confidence,
    )
    return summary
