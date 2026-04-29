"""Mechanical bias updates — pure function that nudges an agent's proposed stance
based on their bias type and strength.

Called after the LLM proposes a new stance, before it's finalized. This ensures
biases leave a measurable trace on trajectories, not just dialogue.

Each bias gets its own update rule, parameterized by the agent's bias_strength.
Not every bias has a mechanical effect — some are text-only (the LLM handles them
through behavioral cues in the prompt). This is documented per-bias below.

PLACEHOLDER: All coefficients below are initial guesses, NOT calibrated.
A calibration harness (bias_calibration.py) with toy scenarios should be built
to validate each value. Until then, treat these as tunable starting points.
The unit tests verify directional correctness (anchoring pulls toward initial,
bandwagon pulls toward aggregate, etc.) but not magnitude.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ── Bias coefficients ────────────────────────────────────────────────────────
# Each coefficient is the maximum nudge at bias_strength=1.0. The actual nudge
# is coefficient × bias_strength.
#
# THESE ARE PLACEHOLDERS. They were chosen to be:
#   - Large enough to be visible over 10-20 ticks
#   - Small enough not to override the LLM's reasoning entirely
#   - Ordered by intended effect strength (pull biases > amplify biases > drift biases)
# They need a calibration harness to validate. See the roadmap's Step 5.

# Anchoring: pull proposed stance back toward initial_stance.
# Placeholder — intended to keep agents within ~1 spectrum bin of their start.
ANCHORING_PULL_COEFFICIENT = 0.15

# Status quo: pull proposed stance back toward previous_stance.
# Placeholder — same magnitude as anchoring since the mechanic is identical.
STATUS_QUO_PULL_COEFFICIENT = 0.15

# Bandwagon: pull proposed stance toward aggregate_stance.
# Placeholder — slightly weaker than anchoring; drift, not snap.
BANDWAGON_PULL_COEFFICIENT = 0.12

# Loss aversion: asymmetric — moves toward "oppose" (lower stance) amplify,
# moves toward "support" (higher stance) dampen.
# Placeholder — should create visible asymmetry without spiraling agents to 0.
LOSS_AVERSION_AMPLIFY_COEFFICIENT = 0.10

# Confirmation bias: amplify moves in the direction of current stance,
# dampen reversals.
# Placeholder — intentionally mild; too strong and agents never change their minds.
CONFIRMATION_AMPLIFY_COEFFICIENT = 0.08

# Optimism bias: small persistent pull toward the "support" end (1.0).
# Placeholder — should be subtle but measurable over 10+ ticks.
OPTIMISM_PULL_COEFFICIENT = 0.04

# Negativity bias: small persistent pull toward the "oppose" end (0.0).
# Placeholder — symmetric with optimism for fairness.
NEGATIVITY_PULL_COEFFICIENT = 0.04

# Recency bias: amplify the current tick's delta.
# Placeholder — the LLM already reacts to recent messages; this just amplifies.
RECENCY_AMPLIFY_COEFFICIENT = 0.10

# Sunk cost: resist reversals — penalizes direction changes, not just movement.
# Placeholder — should dampen reversals without freezing agents.
SUNK_COST_REVERSAL_DAMPEN = 0.12

# Overconfidence: amplify moves away from neutral (0.5).
# Placeholder — mild; doubles down on whatever direction the agent is leaning.
OVERCONFIDENCE_AMPLIFY_COEFFICIENT = 0.06


# ── Biases with text-only effects (no mechanical update) ─────────────────────
# These biases are handled entirely through behavioral cues in the LLM prompt.
# They don't have a clean mathematical formulation that wouldn't just be noise.
#
# - authority_bias: depends on which agents are "authorities" — context-dependent
# - availability_heuristic: depends on what examples are "available" — LLM handles
# - dunning_kruger: about confidence in reasoning, not stance direction
# - framing_effect: depends on how information is framed — LLM handles
# - in_group_bias: depends on group membership — context-dependent
TEXT_ONLY_BIASES = frozenset({
    "authority_bias",
    "availability_heuristic",
    "dunning_kruger",
    "framing_effect",
    "in_group_bias",
})


def apply_bias(
    bias_id: str,
    bias_strength: float,
    proposed_stance: float,
    previous_stance: float,
    initial_stance: float,
    aggregate_stance: float,
) -> float:
    """Apply mechanical bias correction to a proposed stance.

    Pure function — deterministic for fixed inputs. Returns the corrected stance,
    clamped to [0.0, 1.0].

    Args:
        bias_id: canonical bias ID from the catalog
        bias_strength: 0.0–1.0, how strongly the bias applies
        proposed_stance: the stance the LLM proposed for this tick
        previous_stance: the agent's stance from the previous tick
        initial_stance: the agent's starting stance (tick 0)
        aggregate_stance: the current aggregate stance of all agents

    Returns:
        Corrected stance, clamped to [0.0, 1.0].
    """
    # Zero strength = no-op (the function is identity)
    if bias_strength <= 0.0:
        return proposed_stance

    # Text-only biases have no mechanical effect
    if bias_id in TEXT_ONLY_BIASES:
        return proposed_stance

    # Defensive: if proposed_stance is None (shouldn't happen but LLM can be weird),
    # treat as no-op
    if proposed_stance is None:
        return previous_stance

    delta = proposed_stance - previous_stance
    corrected = proposed_stance

    if bias_id == "anchoring":
        # Pull toward initial_stance
        pull = (initial_stance - proposed_stance) * ANCHORING_PULL_COEFFICIENT * bias_strength
        corrected = proposed_stance + pull

    elif bias_id == "status_quo_bias":
        # Pull toward previous_stance (resist change)
        pull = (previous_stance - proposed_stance) * STATUS_QUO_PULL_COEFFICIENT * bias_strength
        corrected = proposed_stance + pull

    elif bias_id == "bandwagon_effect":
        # Pull toward aggregate_stance
        pull = (aggregate_stance - proposed_stance) * BANDWAGON_PULL_COEFFICIENT * bias_strength
        corrected = proposed_stance + pull

    elif bias_id == "loss_aversion":
        # Asymmetric: amplify negative moves, dampen positive moves
        coeff = LOSS_AVERSION_AMPLIFY_COEFFICIENT * bias_strength
        if delta < 0:
            # Moving toward oppose — amplify
            corrected = proposed_stance + delta * coeff
        elif delta > 0:
            # Moving toward support — dampen
            corrected = proposed_stance - delta * coeff

    elif bias_id == "confirmation_bias":
        # Amplify moves in the direction of current stance, dampen reversals
        coeff = CONFIRMATION_AMPLIFY_COEFFICIENT * bias_strength
        # Direction of current stance relative to neutral
        current_direction = 1.0 if previous_stance >= 0.5 else -1.0
        if delta * current_direction > 0:
            # Moving in same direction as current lean — amplify
            corrected = proposed_stance + delta * coeff
        elif delta * current_direction < 0:
            # Reversing — dampen
            corrected = proposed_stance - delta * coeff

    elif bias_id == "optimism_bias":
        # Small persistent pull toward 1.0 (support end)
        pull = (1.0 - proposed_stance) * OPTIMISM_PULL_COEFFICIENT * bias_strength
        corrected = proposed_stance + pull

    elif bias_id == "negativity_bias":
        # Small persistent pull toward 0.0 (oppose end)
        pull = (0.0 - proposed_stance) * NEGATIVITY_PULL_COEFFICIENT * bias_strength
        corrected = proposed_stance + pull

    elif bias_id == "recency_bias":
        # Amplify the current tick's delta
        corrected = proposed_stance + delta * RECENCY_AMPLIFY_COEFFICIENT * bias_strength

    elif bias_id == "sunk_cost_fallacy":
        # Resist direction reversals (not just any movement)
        # A reversal is when delta has opposite sign to (previous - initial)
        trend = previous_stance - initial_stance
        if trend != 0 and delta != 0:
            if (trend > 0 and delta < 0) or (trend < 0 and delta > 0):
                # Reversal detected — dampen
                dampen = delta * SUNK_COST_REVERSAL_DAMPEN * bias_strength
                corrected = proposed_stance - dampen

    elif bias_id == "overconfidence":
        # Amplify moves away from neutral (0.5)
        distance_from_neutral = proposed_stance - 0.5
        corrected = proposed_stance + distance_from_neutral * OVERCONFIDENCE_AMPLIFY_COEFFICIENT * bias_strength

    # Clamp to valid range
    corrected = max(0.0, min(1.0, corrected))

    if abs(corrected - proposed_stance) > 0.001:
        logger.debug(
            "Bias correction bias=%s strength=%.2f proposed=%.3f → corrected=%.3f (delta=%.4f)",
            bias_id, bias_strength, proposed_stance, corrected, corrected - proposed_stance,
        )

    return round(corrected, 4)
