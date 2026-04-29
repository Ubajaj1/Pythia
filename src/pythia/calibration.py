"""Calibration scoring — measures how well Pythia's predictions match actual outcomes.

All functions are pure and deterministic. No LLM calls.

This is what makes Pythia credible for real decisions: without ground-truth scoring,
the tool can only measure internal consistency (coherence), never actual accuracy.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pythia.models import (
    BacktestCase,
    BacktestResult,
    CalibrationReport,
    CalibrationScore,
    GroundTruthOutcome,
)

logger = logging.getLogger(__name__)


# ── Named constants ──────────────────────────────────────────────────────────

# Predicted and actual aggregate must be on the same side of 0.5, OR within
# this distance of each other, to count as directionally correct.
# 0.1 means if both are between 0.4 and 0.6, we call it a match even if
# they're on opposite sides of 0.5 — the "neutral zone" is genuinely ambiguous.
DIRECTION_CORRECT_THRESHOLD = 0.1

# Maps predicted confidence labels to expected outcome dispersions.
# Used for confidence_match scoring: did the predicted confidence level
# correspond to how clear-cut the actual outcome was?
# Format: {predicted_label: set of actual_labels that count as a match}
CONFIDENCE_MATCH_BANDS: dict[str, set[str]] = {
    "high": {"high", "moderate"},       # high confidence should match clear outcomes
    "moderate": {"high", "moderate", "low"},  # moderate is the catch-all
    "low": {"low", "moderate"},         # low confidence should match ambiguous outcomes
    "polarized": {"polarized", "low", "moderate"},  # polarized matches uncertain outcomes
}


def compute_calibration_score(
    predicted_aggregate: float,
    predicted_confidence: str,
    actual: GroundTruthOutcome,
) -> CalibrationScore:
    """Score a single prediction against ground truth.

    Pure function — deterministic for fixed inputs.
    """
    # Direction correctness
    pred_side = predicted_aggregate - 0.5
    actual_side = actual.aggregate_stance - 0.5
    distance = abs(predicted_aggregate - actual.aggregate_stance)

    if distance <= DIRECTION_CORRECT_THRESHOLD:
        # Both in the neutral zone — call it correct
        direction_correct = True
    elif pred_side == 0.0 or actual_side == 0.0:
        # One is exactly neutral — correct if the other is within threshold
        direction_correct = distance <= DIRECTION_CORRECT_THRESHOLD
    else:
        # Same sign = same side of 0.5
        direction_correct = (pred_side > 0) == (actual_side > 0)

    # Aggregate error
    aggregate_error = round(abs(predicted_aggregate - actual.aggregate_stance), 4)

    # Confidence match
    allowed = CONFIDENCE_MATCH_BANDS.get(predicted_confidence, set())
    confidence_match = actual.confidence in allowed

    return CalibrationScore(
        direction_correct=direction_correct,
        aggregate_error=aggregate_error,
        confidence_match=confidence_match,
    )


def compute_calibration_report(results: list[BacktestResult]) -> CalibrationReport:
    """Aggregate calibration metrics across multiple backtest results.

    Pure function — deterministic for fixed inputs.
    """
    n = len(results)
    if n == 0:
        return CalibrationReport(
            total_cases=0,
            direction_accuracy=0.0,
            mean_aggregate_error=0.0,
            confidence_match_rate=0.0,
            results=[],
        )

    direction_correct = sum(1 for r in results if r.calibration.direction_correct)
    total_error = sum(r.calibration.aggregate_error for r in results)
    confidence_matches = sum(1 for r in results if r.calibration.confidence_match)

    return CalibrationReport(
        total_cases=n,
        direction_accuracy=round(direction_correct / n, 4),
        mean_aggregate_error=round(total_error / n, 4),
        confidence_match_rate=round(confidence_matches / n, 4),
        results=results,
    )


def load_ground_truth_cases(ground_truth_dir: str = "data/ground_truth") -> list[BacktestCase]:
    """Load all ground-truth cases from JSON files in the given directory.

    Each file should contain a single BacktestCase JSON object.
    Files that fail to parse are logged and skipped.
    """
    gt_path = Path(ground_truth_dir)
    if not gt_path.exists():
        logger.warning("Ground truth directory does not exist: %s", ground_truth_dir)
        return []

    cases = []
    for f in sorted(gt_path.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            case = BacktestCase.model_validate(data)
            if not case.case_id:
                case = case.model_copy(update={"case_id": f.stem})
            cases.append(case)
        except Exception as exc:
            logger.warning("Failed to load ground truth case %s: %s", f.name, exc)

    logger.info("Loaded %d ground truth cases from %s", len(cases), ground_truth_dir)
    return cases
