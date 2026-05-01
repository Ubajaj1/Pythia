"""Tests for mechanical bias updates — apply_bias must be deterministic and well-behaved."""

import pytest
from pythia.bias_mechanics import apply_bias, TEXT_ONLY_BIASES


class TestApplyBiasBasics:
    """Core properties that must hold for all biases."""

    def test_zero_strength_is_noop(self):
        """Zero bias_strength means the function returns the proposed stance unchanged."""
        for bias in ["anchoring", "loss_aversion", "bandwagon_effect", "status_quo_bias"]:
            result = apply_bias(
                bias_id=bias, bias_strength=0.0,
                proposed_stance=0.8, previous_stance=0.5,
                initial_stance=0.3, aggregate_stance=0.6,
            )
            assert result == 0.8, f"{bias} with strength=0 should be no-op"

    def test_result_always_clamped(self):
        """Output is always in [0.0, 1.0] regardless of inputs."""
        for bias in ["anchoring", "optimism_bias", "negativity_bias", "loss_aversion"]:
            result = apply_bias(
                bias_id=bias, bias_strength=1.0,
                proposed_stance=0.99, previous_stance=0.01,
                initial_stance=0.01, aggregate_stance=0.99,
            )
            assert 0.0 <= result <= 1.0

    def test_text_only_biases_are_noop(self):
        """Biases in TEXT_ONLY_BIASES have no mechanical effect."""
        for bias in TEXT_ONLY_BIASES:
            result = apply_bias(
                bias_id=bias, bias_strength=1.0,
                proposed_stance=0.7, previous_stance=0.5,
                initial_stance=0.3, aggregate_stance=0.6,
            )
            assert result == 0.7, f"{bias} should be text-only (no-op)"

    def test_unknown_bias_is_noop(self):
        """Unknown bias IDs pass through unchanged."""
        result = apply_bias(
            bias_id="totally_unknown", bias_strength=1.0,
            proposed_stance=0.7, previous_stance=0.5,
            initial_stance=0.3, aggregate_stance=0.6,
        )
        assert result == 0.7

    def test_deterministic(self):
        """Same inputs always produce same output."""
        kwargs = dict(
            bias_id="anchoring", bias_strength=0.8,
            proposed_stance=0.7, previous_stance=0.5,
            initial_stance=0.3, aggregate_stance=0.6,
        )
        results = [apply_bias(**kwargs) for _ in range(10)]
        assert len(set(results)) == 1


class TestAnchoring:
    def test_pulls_toward_initial(self):
        """Anchoring should pull the proposed stance back toward initial_stance."""
        result = apply_bias(
            bias_id="anchoring", bias_strength=1.0,
            proposed_stance=0.9, previous_stance=0.5,
            initial_stance=0.3, aggregate_stance=0.6,
        )
        # Should be pulled back from 0.9 toward 0.3
        assert result < 0.9
        assert result > 0.3  # shouldn't overshoot

    def test_no_effect_when_at_initial(self):
        """No pull when proposed stance equals initial stance."""
        result = apply_bias(
            bias_id="anchoring", bias_strength=1.0,
            proposed_stance=0.3, previous_stance=0.3,
            initial_stance=0.3, aggregate_stance=0.5,
        )
        assert result == 0.3


class TestStatusQuo:
    def test_resists_change(self):
        """Status quo should pull proposed stance back toward previous stance."""
        result = apply_bias(
            bias_id="status_quo_bias", bias_strength=1.0,
            proposed_stance=0.8, previous_stance=0.5,
            initial_stance=0.5, aggregate_stance=0.6,
        )
        assert result < 0.8  # pulled back toward 0.5


class TestBandwagon:
    def test_pulls_toward_aggregate(self):
        """Bandwagon should pull proposed stance toward aggregate."""
        result = apply_bias(
            bias_id="bandwagon_effect", bias_strength=1.0,
            proposed_stance=0.3, previous_stance=0.3,
            initial_stance=0.3, aggregate_stance=0.8,
        )
        assert result > 0.3  # pulled toward 0.8


class TestLossAversion:
    def test_asymmetric_negative_amplified(self):
        """Negative moves (toward oppose) should be amplified."""
        result = apply_bias(
            bias_id="loss_aversion", bias_strength=1.0,
            proposed_stance=0.3, previous_stance=0.5,
            initial_stance=0.5, aggregate_stance=0.5,
        )
        # delta = -0.2, amplified → result should be < 0.3
        assert result < 0.3

    def test_asymmetric_positive_dampened(self):
        """Positive moves (toward support) should be dampened."""
        result = apply_bias(
            bias_id="loss_aversion", bias_strength=1.0,
            proposed_stance=0.7, previous_stance=0.5,
            initial_stance=0.5, aggregate_stance=0.5,
        )
        # delta = +0.2, dampened → result should be < 0.7
        assert result < 0.7


class TestOptimismAndNegativity:
    def test_optimism_pulls_toward_support(self):
        result = apply_bias(
            bias_id="optimism_bias", bias_strength=1.0,
            proposed_stance=0.5, previous_stance=0.5,
            initial_stance=0.5, aggregate_stance=0.5,
        )
        assert result > 0.5  # pulled toward 1.0

    def test_negativity_pulls_toward_oppose(self):
        result = apply_bias(
            bias_id="negativity_bias", bias_strength=1.0,
            proposed_stance=0.5, previous_stance=0.5,
            initial_stance=0.5, aggregate_stance=0.5,
        )
        assert result < 0.5  # pulled toward 0.0


class TestConfirmationBias:
    def test_amplifies_same_direction(self):
        """If agent leans support (>0.5) and moves further support, amplify."""
        result = apply_bias(
            bias_id="confirmation_bias", bias_strength=1.0,
            proposed_stance=0.8, previous_stance=0.7,
            initial_stance=0.5, aggregate_stance=0.6,
        )
        # delta = +0.1, same direction as lean (>0.5) → amplified
        assert result > 0.8

    def test_dampens_reversal(self):
        """If agent leans support (>0.5) and moves toward oppose, dampen."""
        result = apply_bias(
            bias_id="confirmation_bias", bias_strength=1.0,
            proposed_stance=0.5, previous_stance=0.7,
            initial_stance=0.5, aggregate_stance=0.6,
        )
        # delta = -0.2, opposite to lean (>0.5) → dampened (pulled back up)
        assert result > 0.5


class TestSunkCost:
    def test_dampens_reversal(self):
        """Sunk cost should resist reversing a trend."""
        result = apply_bias(
            bias_id="sunk_cost_fallacy", bias_strength=1.0,
            proposed_stance=0.4, previous_stance=0.7,
            initial_stance=0.5, aggregate_stance=0.6,
        )
        # Trend was upward (0.5 → 0.7), now reversing (0.7 → 0.4)
        # Should dampen the reversal
        assert result > 0.4
