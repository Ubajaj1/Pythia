"""Temple of Learning — amends agent behavioral_rules and bias_strength after failures.

Three modes of operation:
1. Coherence mode (default): amends agents whose reasoning was incoherent.
2. Ensemble-aware mode (Temple upgrade 2): only amends agents failing in ≥ majority of runs.
3. Accuracy mode (Temple upgrade 3): in past_event mode, amends agents whose final stance
   was far from the actual outcome, using the outcome to inform the amendment.

Rule management (Temple upgrade 1):
- Rule cap: after MAX_RULES_PER_AGENT rules, Temple must edit or remove an existing rule
  instead of adding a new one.
- Bias strength adjustment: Temple can recommend raising or lowering bias_strength based
  on whether the agent's bias was too weak or too strong.
"""

from __future__ import annotations

import logging
import math

from pythia.llm import LLMClient
from pythia.models import Agent, AgentEvaluation, GroundTruthOutcome, TickEvent

logger = logging.getLogger(__name__)


# ── Named constants ──────────────────────────────────────────────────────────

# Maximum behavioral rules per agent. After this, Temple must edit/remove
# instead of adding. Prevents rule bloat that makes agents worse after ~4
# oracle iterations.
MAX_RULES_PER_AGENT = 8

# Minimum fraction of ensemble runs an agent must fail in to trigger amendment.
# At N=3, 0.5 means failing in 2+ runs. At N=1, any failure triggers amendment.
ENSEMBLE_MAJORITY_THRESHOLD = 0.5

# In accuracy mode, agents whose final stance is farther than this from the
# actual outcome get sent to the Temple. On a 0–1 scale, 0.25 means the agent
# was more than one spectrum bin away from reality.
ACCURACY_AMENDMENT_THRESHOLD = 0.25

# Bias strength adjustment step size. Temple nudges bias_strength up or down
# by this amount per amendment. Small enough to be gradual, large enough to
# be visible after 2-3 oracle iterations.
BIAS_STRENGTH_STEP = 0.1


TEMPLE_SYSTEM = """\
You are helping an AI simulation agent learn from its reasoning failures.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON."""


# ── Coherence amendment (original + rule cap) ────────────────────────────────

TEMPLE_PROMPT_ADD = """\
Agent: {name} ({role})
Cognitive bias: {bias} (strength: {bias_strength:.1f})

Current behavioral rules:
{rules}

Why this agent's reasoning was flagged:
{failure_reason}

Agent's action history in this run:
{history}

Task: Add 1-3 new behavioral rules that would prevent this failure in future runs.
Also assess the agent's bias strength:
- If the agent ignored their bias entirely, recommend RAISING bias_strength.
- If the agent was too rigidly biased and couldn't adapt, recommend LOWERING it.
- If bias strength seems appropriate, recommend NO CHANGE.

Guidelines:
- DO NOT remove or restate existing rules.
- ADD rules that capture context-sensitive nuance.
- The goal is richer, more honest reasoning — not forcing conformity.

Respond with ONLY this JSON:
{{"new_rules": ["rule 1", "rule 2"], "bias_strength_adjustment": "raise" | "lower" | "none"}}"""


TEMPLE_PROMPT_EDIT = """\
Agent: {name} ({role})
Cognitive bias: {bias} (strength: {bias_strength:.1f})

Current behavioral rules (AT CAPACITY — {rule_count}/{max_rules}):
{rules}

Why this agent's reasoning was flagged:
{failure_reason}

Agent's action history in this run:
{history}

Task: The agent has too many rules. You must EDIT or REPLACE existing rules instead of adding new ones.
- Identify 1-2 rules that are redundant, contradictory, or least useful.
- Replace them with better rules that address the current failure.
- Also assess bias strength (raise/lower/none).

Respond with ONLY this JSON:
{{"rules_to_remove": ["exact text of rule to remove"], "rules_to_add": ["replacement rule"], "bias_strength_adjustment": "raise" | "lower" | "none"}}"""


# ── Accuracy amendment (Temple upgrade 3) ────────────────────────────────────

TEMPLE_PROMPT_ACCURACY = """\
Agent: {name} ({role})
Cognitive bias: {bias} (strength: {bias_strength:.1f})

Current behavioral rules:
{rules}

ACCURACY FAILURE — this agent's prediction was wrong:
- Agent's final stance: {agent_final_stance:.2f}
- Actual outcome: {actual_stance:.2f}
- Error: {error:.2f}
- The agent was too far {direction} compared to reality.

What actually happened: {outcome_notes}

Agent's action history:
{history}

Task: Add 1-2 rules that capture what signals this agent should have weighted more heavily.
The goal is domain calibration — help this agent make better predictions in similar future scenarios.
Also assess bias strength relative to the outcome.

Respond with ONLY this JSON:
{{"new_rules": ["rule 1"], "bias_strength_adjustment": "raise" | "lower" | "none"}}"""


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


def _apply_bias_adjustment(agent: Agent, adjustment: str) -> float:
    """Compute new bias_strength based on Temple's recommendation."""
    current = agent.bias_strength
    if adjustment == "raise":
        return min(1.0, current + BIAS_STRENGTH_STEP)
    elif adjustment == "lower":
        return max(0.0, current - BIAS_STRENGTH_STEP)
    return current


async def amend_agent(
    agent: Agent,
    evaluation: AgentEvaluation,
    tick_pairs: list[tuple[int, TickEvent]],
    llm: LLMClient,
) -> Agent:
    """Amend agent after coherence failure. Handles rule cap and bias strength.

    Returns original agent if evaluation is coherent.
    """
    if evaluation.is_coherent:
        return agent

    logger.info(
        "Temple: amending agent=%s incoherence=%r rules=%d/%d",
        agent.name, evaluation.incoherence_summary,
        len(agent.behavioral_rules), MAX_RULES_PER_AGENT,
    )

    failure_reason = evaluation.incoherence_summary or "Reasoning did not explain action"
    history = _format_history(tick_pairs)

    if len(agent.behavioral_rules) >= MAX_RULES_PER_AGENT:
        # Edit mode — at capacity, must replace rules
        return await _amend_edit_mode(agent, failure_reason, history, llm)
    else:
        # Add mode — room for new rules
        return await _amend_add_mode(agent, failure_reason, history, llm)


async def _amend_add_mode(
    agent: Agent, failure_reason: str, history: str, llm: LLMClient,
) -> Agent:
    """Add new rules (original behavior + bias strength adjustment)."""
    prompt = TEMPLE_PROMPT_ADD.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        bias_strength=agent.bias_strength,
        rules=_format_rules(agent.behavioral_rules),
        failure_reason=failure_reason,
        history=history,
    )

    raw = await llm.generate(prompt=prompt, system=TEMPLE_SYSTEM)
    new_rules = [r for r in raw.get("new_rules", []) if isinstance(r, str)]
    adjustment = str(raw.get("bias_strength_adjustment", "none")).lower()
    new_strength = _apply_bias_adjustment(agent, adjustment)

    # Cap new rules so we don't exceed MAX_RULES_PER_AGENT
    room = MAX_RULES_PER_AGENT - len(agent.behavioral_rules)
    new_rules = new_rules[:room]

    logger.info(
        "Temple (add): agent=%s +%d rules, bias_strength %.2f→%.2f (%s)",
        agent.name, len(new_rules), agent.bias_strength, new_strength, adjustment,
    )

    return agent.model_copy(update={
        "behavioral_rules": agent.behavioral_rules + new_rules,
        "bias_strength": new_strength,
    })


async def _amend_edit_mode(
    agent: Agent, failure_reason: str, history: str, llm: LLMClient,
) -> Agent:
    """Edit/replace rules when at capacity."""
    prompt = TEMPLE_PROMPT_EDIT.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        bias_strength=agent.bias_strength,
        rule_count=len(agent.behavioral_rules),
        max_rules=MAX_RULES_PER_AGENT,
        rules=_format_rules(agent.behavioral_rules),
        failure_reason=failure_reason,
        history=history,
    )

    raw = await llm.generate(prompt=prompt, system=TEMPLE_SYSTEM)
    rules_to_remove = [r for r in raw.get("rules_to_remove", []) if isinstance(r, str)]
    rules_to_add = [r for r in raw.get("rules_to_add", []) if isinstance(r, str)]
    adjustment = str(raw.get("bias_strength_adjustment", "none")).lower()
    new_strength = _apply_bias_adjustment(agent, adjustment)

    # Remove specified rules (fuzzy match — strip whitespace)
    current_rules = list(agent.behavioral_rules)
    removed_count = 0
    for to_remove in rules_to_remove:
        stripped = to_remove.strip()
        for i, rule in enumerate(current_rules):
            if rule.strip() == stripped:
                current_rules.pop(i)
                removed_count += 1
                break

    # Add new rules (respect cap)
    room = MAX_RULES_PER_AGENT - len(current_rules)
    rules_to_add = rules_to_add[:room]
    current_rules.extend(rules_to_add)

    logger.info(
        "Temple (edit): agent=%s -%d +%d rules (now %d/%d), bias_strength %.2f→%.2f (%s)",
        agent.name, removed_count, len(rules_to_add),
        len(current_rules), MAX_RULES_PER_AGENT,
        agent.bias_strength, new_strength, adjustment,
    )

    return agent.model_copy(update={
        "behavioral_rules": current_rules,
        "bias_strength": new_strength,
    })


# ── Accuracy-based amendment (Temple upgrade 3) ─────────────────────────────

async def amend_agent_accuracy(
    agent: Agent,
    agent_final_stance: float,
    ground_truth: GroundTruthOutcome,
    tick_pairs: list[tuple[int, TickEvent]],
    llm: LLMClient,
) -> Agent:
    """Amend agent based on accuracy vs actual outcome (past_event mode).

    Only amends if the agent's final stance was far from the actual outcome.
    Uses the outcome to inform what signals the agent should have weighted more.
    """
    error = abs(agent_final_stance - ground_truth.aggregate_stance)
    if error < ACCURACY_AMENDMENT_THRESHOLD:
        logger.info(
            "Temple (accuracy): agent=%s error=%.3f < threshold=%.3f — no amendment needed",
            agent.name, error, ACCURACY_AMENDMENT_THRESHOLD,
        )
        return agent

    direction = "optimistic (too high)" if agent_final_stance > ground_truth.aggregate_stance else "pessimistic (too low)"

    logger.info(
        "Temple (accuracy): amending agent=%s final=%.2f actual=%.2f error=%.3f direction=%s",
        agent.name, agent_final_stance, ground_truth.aggregate_stance, error, direction,
    )

    prompt = TEMPLE_PROMPT_ACCURACY.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        bias_strength=agent.bias_strength,
        rules=_format_rules(agent.behavioral_rules),
        agent_final_stance=agent_final_stance,
        actual_stance=ground_truth.aggregate_stance,
        error=error,
        direction=direction,
        outcome_notes=ground_truth.notes or "No additional details provided.",
        history=_format_history(tick_pairs),
    )

    raw = await llm.generate(prompt=prompt, system=TEMPLE_SYSTEM)
    new_rules = [r for r in raw.get("new_rules", []) if isinstance(r, str)]
    adjustment = str(raw.get("bias_strength_adjustment", "none")).lower()
    new_strength = _apply_bias_adjustment(agent, adjustment)

    # Respect rule cap
    room = MAX_RULES_PER_AGENT - len(agent.behavioral_rules)
    if room <= 0:
        # At capacity — only adjust bias strength, skip rules
        logger.info(
            "Temple (accuracy): agent=%s at rule cap, only adjusting bias_strength %.2f→%.2f",
            agent.name, agent.bias_strength, new_strength,
        )
        return agent.model_copy(update={"bias_strength": new_strength})

    new_rules = new_rules[:room]

    logger.info(
        "Temple (accuracy): agent=%s +%d rules, bias_strength %.2f→%.2f (%s)",
        agent.name, len(new_rules), agent.bias_strength, new_strength, adjustment,
    )

    return agent.model_copy(update={
        "behavioral_rules": agent.behavioral_rules + new_rules,
        "bias_strength": new_strength,
    })


# ── Ensemble-aware filtering (Temple upgrade 2) ─────────────────────────────

def filter_ensemble_failures(
    agent_failure_counts: dict[str, int],
    total_runs: int,
) -> set[str]:
    """Return agent IDs that failed in a majority of ensemble runs.

    An agent flagged incoherent in 1 of 3 runs is noise.
    An agent flagged in 2+ of 3 runs is a real signal.

    Args:
        agent_failure_counts: {agent_id: number_of_runs_where_incoherent}
        total_runs: total number of ensemble runs

    Returns:
        Set of agent IDs that should be amended.
    """
    if total_runs <= 1:
        # Single run — amend all failures (no ensemble filtering)
        return {aid for aid, count in agent_failure_counts.items() if count > 0}

    # For N≥2, require strict majority: ceil(N * threshold)
    # At N=3, threshold=0.5 → ceil(1.5) = 2 (must fail in 2+ runs)
    # At N=5, threshold=0.5 → ceil(2.5) = 3 (must fail in 3+ runs)
    threshold = math.ceil(total_runs * ENSEMBLE_MAJORITY_THRESHOLD)
    # Ensure at least 2 for ensemble mode — a single failure is always noise
    threshold = max(2, threshold)
    amended = set()
    for agent_id, fail_count in agent_failure_counts.items():
        if fail_count >= threshold:
            amended.add(agent_id)
            logger.info(
                "Ensemble filter: agent=%s failed %d/%d runs (≥%d) — will amend",
                agent_id, fail_count, total_runs, threshold,
            )
        else:
            logger.info(
                "Ensemble filter: agent=%s failed %d/%d runs (<%d) — noise, skipping",
                agent_id, fail_count, total_runs, threshold,
            )
    return amended
