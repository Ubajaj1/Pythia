"""Tests for calibration scoring — Step 8 ground-truth mode."""

import json
import pytest
from pathlib import Path

from pythia.calibration import (
    DIRECTION_CORRECT_THRESHOLD,
    CONFIDENCE_MATCH_BANDS,
    compute_calibration_score,
    compute_calibration_report,
    load_ground_truth_cases,
)
from pythia.models import (
    BacktestResult,
    CalibrationScore,
    GroundTruthOutcome,
)


class TestComputeCalibrationScore:
    """Pure function tests — deterministic, no LLM."""

    def test_perfect_match(self):
        score = compute_calibration_score(
            predicted_aggregate=0.75,
            predicted_confidence="high",
            actual=GroundTruthOutcome(aggregate_stance=0.75, confidence="high"),
        )
        assert score.direction_correct is True
        assert score.aggregate_error == 0.0
        assert score.confidence_match is True

    def test_same_direction_different_magnitude(self):
        score = compute_calibration_score(
            predicted_aggregate=0.8,
            predicted_confidence="high",
            actual=GroundTruthOutcome(aggregate_stance=0.65, confidence="high"),
        )
        assert score.direction_correct is True  # both > 0.5
        assert score.aggregate_error == pytest.approx(0.15, abs=0.001)

    def test_opposite_direction(self):
        score = compute_calibration_score(
            predicted_aggregate=0.7,
            predicted_confidence="high",
            actual=GroundTruthOutcome(aggregate_stance=0.3, confidence="low"),
        )
        assert score.direction_correct is False  # 0.7 > 0.5, 0.3 < 0.5
        assert score.aggregate_error == pytest.approx(0.4, abs=0.001)

    def test_both_near_neutral_counts_as_correct(self):
        """If both predicted and actual are within DIRECTION_CORRECT_THRESHOLD of each other,
        direction is correct even if they're on opposite sides of 0.5."""
        score = compute_calibration_score(
            predicted_aggregate=0.48,
            predicted_confidence="low",
            actual=GroundTruthOutcome(aggregate_stance=0.52, confidence="low"),
        )
        # Distance = 0.04 < DIRECTION_CORRECT_THRESHOLD (0.1)
        assert score.direction_correct is True

    def test_aggregate_exactly_0_5(self):
        score = compute_calibration_score(
            predicted_aggregate=0.5,
            predicted_confidence="low",
            actual=GroundTruthOutcome(aggregate_stance=0.5, confidence="low"),
        )
        assert score.direction_correct is True
        assert score.aggregate_error == 0.0

    def test_confidence_match_high_to_moderate(self):
        """High confidence matching moderate outcome should count as a match."""
        score = compute_calibration_score(
            predicted_aggregate=0.7,
            predicted_confidence="high",
            actual=GroundTruthOutcome(aggregate_stance=0.7, confidence="moderate"),
        )
        assert score.confidence_match is True

    def test_confidence_mismatch_high_to_low(self):
        """High confidence with low actual outcome is a mismatch."""
        score = compute_calibration_score(
            predicted_aggregate=0.7,
            predicted_confidence="high",
            actual=GroundTruthOutcome(aggregate_stance=0.7, confidence="low"),
        )
        assert score.confidence_match is False

    def test_confidence_match_low_to_low(self):
        score = compute_calibration_score(
            predicted_aggregate=0.5,
            predicted_confidence="low",
            actual=GroundTruthOutcome(aggregate_stance=0.5, confidence="low"),
        )
        assert score.confidence_match is True

    def test_polarized_matches_uncertain(self):
        score = compute_calibration_score(
            predicted_aggregate=0.5,
            predicted_confidence="polarized",
            actual=GroundTruthOutcome(aggregate_stance=0.5, confidence="low"),
        )
        assert score.confidence_match is True


class TestComputeCalibrationReport:
    def test_empty_results(self):
        report = compute_calibration_report([])
        assert report.total_cases == 0
        assert report.direction_accuracy == 0.0

    def test_single_perfect_result(self):
        result = BacktestResult(
            case_id="c1", prompt="test",
            predicted_aggregate=0.7, predicted_confidence="high",
            actual_aggregate=0.7, actual_confidence="high",
            calibration=CalibrationScore(
                direction_correct=True, aggregate_error=0.0, confidence_match=True,
            ),
            run_id="r1",
        )
        report = compute_calibration_report([result])
        assert report.total_cases == 1
        assert report.direction_accuracy == 1.0
        assert report.mean_aggregate_error == 0.0
        assert report.confidence_match_rate == 1.0

    def test_mixed_results(self):
        results = [
            BacktestResult(
                case_id="c1", prompt="test1",
                predicted_aggregate=0.7, predicted_confidence="high",
                actual_aggregate=0.7, actual_confidence="high",
                calibration=CalibrationScore(
                    direction_correct=True, aggregate_error=0.0, confidence_match=True,
                ),
                run_id="r1",
            ),
            BacktestResult(
                case_id="c2", prompt="test2",
                predicted_aggregate=0.7, predicted_confidence="high",
                actual_aggregate=0.3, actual_confidence="low",
                calibration=CalibrationScore(
                    direction_correct=False, aggregate_error=0.4, confidence_match=False,
                ),
                run_id="r2",
            ),
        ]
        report = compute_calibration_report(results)
        assert report.total_cases == 2
        assert report.direction_accuracy == 0.5
        assert report.mean_aggregate_error == pytest.approx(0.2, abs=0.001)
        assert report.confidence_match_rate == 0.5


class TestLoadGroundTruthCases:
    def test_nonexistent_dir(self):
        cases = load_ground_truth_cases("/nonexistent/path")
        assert cases == []

    def test_loads_valid_json(self, tmp_path):
        case_data = {
            "prompt": "Did the Fed rate hike cause a market crash?",
            "ground_truth_outcome": {
                "aggregate_stance": 0.3,
                "confidence": "high",
                "notes": "S&P dropped 4% in 48 hours",
            },
            "case_id": "fed-rate-2024",
            "domain": "earnings",
        }
        (tmp_path / "case1.json").write_text(json.dumps(case_data))
        cases = load_ground_truth_cases(str(tmp_path))
        assert len(cases) == 1
        assert cases[0].case_id == "fed-rate-2024"
        assert cases[0].ground_truth_outcome.aggregate_stance == 0.3

    def test_skips_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("not valid json {{{")
        (tmp_path / "good.json").write_text(json.dumps({
            "prompt": "test",
            "ground_truth_outcome": {"aggregate_stance": 0.5, "confidence": "low"},
        }))
        cases = load_ground_truth_cases(str(tmp_path))
        assert len(cases) == 1

    def test_assigns_case_id_from_filename(self, tmp_path):
        (tmp_path / "my-case.json").write_text(json.dumps({
            "prompt": "test",
            "ground_truth_outcome": {"aggregate_stance": 0.5, "confidence": "low"},
        }))
        cases = load_ground_truth_cases(str(tmp_path))
        assert cases[0].case_id == "my-case"


class TestNamedConstants:
    def test_direction_threshold_reasonable(self):
        assert 0.0 < DIRECTION_CORRECT_THRESHOLD <= 0.2

    def test_confidence_bands_cover_all_labels(self):
        for label in ["high", "moderate", "low", "polarized"]:
            assert label in CONFIDENCE_MATCH_BANDS
