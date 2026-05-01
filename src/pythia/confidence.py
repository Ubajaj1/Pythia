"""Deterministic confidence scoring from simulation dispersion.

We deliberately do NOT ask the LLM to pick a confidence label — LLMs default to
"moderate" for almost any mixed panel, which hides real signal. Instead we compute
two independent measurements from the final agent stances and label them with
thresholds chosen for a 0–1 stance scale with a 5-bin spectrum.

Two axes, not one:
  1. AGREEMENT  — how tightly clustered are the agents? (population stddev)
  2. CONVICTION — how far is the aggregate from neutral?  (|aggregate − 0.5|)

This produces a 2×2 grid that distinguishes, for example, "everyone weakly agrees"
(tepid) from "everyone strongly agrees" (strong consensus) — two cases a single
"confidence" word cannot tell apart.

All thresholds below are NAMED and COMMENTED. They are rules-of-thumb chosen to
map meaningfully to the 5-label stance spectrum (each label ≈ 0.2 wide), not
laws of nature. Revise with reason, not by feel.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# ── Agreement thresholds (population stddev of final stances, 0–1 scale) ─────
#
# Interpretation of σ on a 5-bin spectrum where each label spans ≈ 0.2:
#   σ < 0.10  → agents are clustered within ~half a spectrum bin
#   σ < 0.20  → agents span roughly one spectrum bin
#   σ ≥ 0.20  → agents span two or more spectrum bins (meaningfully divided)
#
# These are descriptive thresholds for a bounded scale, not calibrated against
# any external dataset. For small N (≤6 agents) σ is itself a noisy estimator;
# ensemble runs (Step 6) will stabilize this.
AGREEMENT_CLUSTERED_MAX = 0.10
AGREEMENT_MIXED_MAX = 0.20

# ── Conviction thresholds (|aggregate − 0.5|, 0–0.5 scale) ───────────────────
#
# On a 5-bin spectrum centered at 0.5:
#   |agg − 0.5| < 0.10  → aggregate falls inside the "neutral" band
#   |agg − 0.5| < 0.20  → aggregate reaches the adjacent "support/oppose" band
#   |agg − 0.5| ≥ 0.20  → aggregate reaches the outer "strongly" band
CONVICTION_TEPID_MAX = 0.10
CONVICTION_MODERATE_MAX = 0.20


@dataclass(frozen=True)
class ConfidenceReading:
    """Result of deterministic dispersion analysis on a set of final stances."""
    agreement: str           # "clustered" | "mixed" | "spread"
    conviction: str          # "strong" | "moderate" | "tepid"
    label: str               # combined verdict — see _combine_labels
    stance_stddev: float
    stance_spread: float
    aggregate: float
    n_agents: int

    @property
    def rationale(self) -> str:
        """Short human-readable explanation of the reading."""
        return (
            f"{self.n_agents} agents, stance σ={self.stance_stddev:.2f} "
            f"({self.agreement}), aggregate {self.aggregate:.2f} "
            f"({self.conviction} conviction)"
        )


def _population_stddev(values: list[float]) -> float:
    """Population (not sample) stddev — we treat the panel as the full population,
    not a sample of some larger group, because there is no larger group.
    """
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _classify_agreement(stddev: float) -> str:
    if stddev < AGREEMENT_CLUSTERED_MAX:
        return "clustered"
    if stddev < AGREEMENT_MIXED_MAX:
        return "mixed"
    return "spread"


def _classify_conviction(aggregate: float) -> str:
    distance_from_neutral = abs(aggregate - 0.5)
    if distance_from_neutral < CONVICTION_TEPID_MAX:
        return "tepid"
    if distance_from_neutral < CONVICTION_MODERATE_MAX:
        return "moderate"
    return "strong"


def _combine_labels(agreement: str, conviction: str) -> str:
    """Map the (agreement, conviction) 2×2 grid into a single headline label.

    Grid:
                    clustered        mixed            spread
        strong  →   high             moderate         polarized
        moderate →  moderate         moderate         polarized
        tepid   →   low              low              low

    Rationale:
    - "high" requires BOTH clustered agreement AND strong conviction away from
      neutral — the only combination that gives a decision-maker a clear signal.
    - "polarized" = agents disagree strongly (spread) despite some conviction.
      This is different from "low" (everyone's just uncertain).
    - "low" captures tepid outcomes regardless of agreement — if aggregate is
      near 0.5, the panel didn't pick a side, and tight clustering around 0.5
      doesn't change that.
    - Everything else is "moderate" — partial signal.
    """
    if conviction == "tepid":
        return "low"
    if agreement == "spread":
        return "polarized"
    if agreement == "clustered" and conviction == "strong":
        return "high"
    return "moderate"


def compute_confidence(final_stances: list[float]) -> ConfidenceReading:
    """Compute a ConfidenceReading from a list of final agent stances.

    Pure function — no LLM calls, no randomness. Given the same inputs, always
    returns the same output. This is the property that makes it trustworthy.
    """
    if not final_stances:
        return ConfidenceReading(
            agreement="clustered", conviction="tepid", label="low",
            stance_stddev=0.0, stance_spread=0.0, aggregate=0.5, n_agents=0,
        )

    aggregate = sum(final_stances) / len(final_stances)
    stddev = _population_stddev(final_stances)
    spread = max(final_stances) - min(final_stances)

    agreement = _classify_agreement(stddev)
    conviction = _classify_conviction(aggregate)
    label = _combine_labels(agreement, conviction)

    return ConfidenceReading(
        agreement=agreement,
        conviction=conviction,
        label=label,
        stance_stddev=round(stddev, 4),
        stance_spread=round(spread, 4),
        aggregate=round(aggregate, 4),
        n_agents=len(final_stances),
    )
