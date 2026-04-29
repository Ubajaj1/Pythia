"""Tests for the Temple of Learning — all three upgrade modes."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.temple import (
    amend_agent,
    amend_agent_accuracy,
    filter_ensemble_failures,
    MAX_RULES_PER_AGENT,
    ENSEMBLE_MAJORITY_THRESHOLD,
    ACCURACY_AMENDMENT_THRESHOLD,
    BIAS_STRENGTH_STEP,
)
from pythia.models import Agent, AgentEvaluation, GroundTruthOutcome, TickEvent


def make_agent(rule_count: int = 2, bias_strength: float = 0.5):
    rules = [f"Rule {i+1}" for i in range(rule_count)]
    return Agent(
        id="agent-a", name="Agent A", role="trader",
        persona="Cautious trader.", bias="loss_aversion",
        bias_strength=bias_strength,
        initial_stance=0.3,
        behavioral_rules=rules,
    )


def make_tick_pairs():
    return [
        (1, TickEvent(
            agent_id="agent-a", stance=0.85, previous_stance=0.3,
            action="buy aggressively", emotion="excited",
            reasoning="FOMO took over",
            message="All in.", influence_target=None,
        ))
    ]


def make_incoherent_eval():
    return AgentEvaluation(
        agent_id="agent-a",
        is_coherent=False,
        incoherence_summary="Agent claimed loss-aversion but bought aggressively",
    )


# ── Original coherence amendment tests ───────────────────────────────────────

class TestAmendAgent:
    async def test_amended_agent_has_more_rules_than_original(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["When FOMO overrides loss-aversion, state the trigger"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        original_count = len(agent.behavioral_rules)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert len(amended.behavioral_rules) > original_count

    async def test_preserves_all_original_rules(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["New rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert "Rule 1" in amended.behavioral_rules
        assert "Rule 2" in amended.behavioral_rules

    async def test_new_rules_appended(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["New rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.behavioral_rules[-1] == "New rule"

    async def test_identity_fields_unchanged(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["New rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.id == "agent-a"
        assert amended.name == "Agent A"
        assert amended.bias == "loss_aversion"
        assert amended.initial_stance == 0.3

    async def test_coherent_agent_returned_unchanged(self):
        llm = FakeLLMClient(responses=[])
        agent = make_agent()
        coherent_eval = AgentEvaluation(
            agent_id="agent-a", is_coherent=True, incoherence_summary=None,
        )
        amended = await amend_agent(agent, coherent_eval, make_tick_pairs(), llm)
        assert amended is agent
        assert len(llm.calls) == 0

    async def test_ignores_non_string_new_rules(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["Valid rule", 42, None, "Another valid"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        added = amended.behavioral_rules[len(agent.behavioral_rules):]
        assert added == ["Valid rule", "Another valid"]

    async def test_empty_new_rules_preserves_rules(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.behavioral_rules == agent.behavioral_rules


# ── Temple Upgrade 1: Rule cap + bias strength ──────────────────────────────

class TestRuleCap:
    async def test_add_mode_respects_cap(self):
        """When near the cap, only add enough rules to reach it."""
        llm = FakeLLMClient(responses=[{
            "new_rules": ["Rule A", "Rule B", "Rule C"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent(rule_count=MAX_RULES_PER_AGENT - 1)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert len(amended.behavioral_rules) == MAX_RULES_PER_AGENT

    async def test_edit_mode_triggered_at_cap(self):
        """When at the cap, Temple uses edit mode (remove + add)."""
        llm = FakeLLMClient(responses=[{
            "rules_to_remove": ["Rule 1"],
            "rules_to_add": ["Better rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent(rule_count=MAX_RULES_PER_AGENT)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert "Rule 1" not in amended.behavioral_rules
        assert "Better rule" in amended.behavioral_rules
        assert len(amended.behavioral_rules) <= MAX_RULES_PER_AGENT

    async def test_edit_mode_preserves_unremoved_rules(self):
        llm = FakeLLMClient(responses=[{
            "rules_to_remove": ["Rule 1"],
            "rules_to_add": ["Replacement"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent(rule_count=MAX_RULES_PER_AGENT)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        # Rule 2 through Rule N should still be there
        assert "Rule 2" in amended.behavioral_rules

    async def test_edit_mode_no_match_keeps_all_rules(self):
        """If the LLM suggests removing a rule that doesn't exist, nothing is removed."""
        llm = FakeLLMClient(responses=[{
            "rules_to_remove": ["Nonexistent rule"],
            "rules_to_add": ["New rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent(rule_count=MAX_RULES_PER_AGENT)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        # Can't add because at cap and nothing was removed
        assert len(amended.behavioral_rules) == MAX_RULES_PER_AGENT


class TestBiasStrengthAdjustment:
    async def test_raise_increases_strength(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "raise",
        }])
        agent = make_agent(bias_strength=0.5)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.bias_strength == pytest.approx(0.5 + BIAS_STRENGTH_STEP)

    async def test_lower_decreases_strength(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "lower",
        }])
        agent = make_agent(bias_strength=0.5)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.bias_strength == pytest.approx(0.5 - BIAS_STRENGTH_STEP)

    async def test_none_keeps_strength(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent(bias_strength=0.5)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.bias_strength == 0.5

    async def test_raise_clamped_at_1(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "raise",
        }])
        agent = make_agent(bias_strength=0.95)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.bias_strength == 1.0

    async def test_lower_clamped_at_0(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": [],
            "bias_strength_adjustment": "lower",
        }])
        agent = make_agent(bias_strength=0.05)
        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_pairs(), llm)
        assert amended.bias_strength == 0.0


# ── Temple Upgrade 2: Ensemble-aware filtering ──────────────────────────────

class TestEnsembleFiltering:
    def test_single_run_amends_all_failures(self):
        counts = {"agent-a": 1, "agent-b": 0}
        result = filter_ensemble_failures(counts, total_runs=1)
        assert result == {"agent-a"}

    def test_three_runs_majority_amends(self):
        counts = {"agent-a": 2, "agent-b": 1}
        result = filter_ensemble_failures(counts, total_runs=3)
        assert "agent-a" in result  # 2/3 ≥ threshold
        assert "agent-b" not in result  # 1/3 < threshold

    def test_three_runs_all_fail_amends(self):
        counts = {"agent-a": 3}
        result = filter_ensemble_failures(counts, total_runs=3)
        assert "agent-a" in result

    def test_three_runs_noise_skipped(self):
        counts = {"agent-a": 1, "agent-b": 1, "agent-c": 1}
        result = filter_ensemble_failures(counts, total_runs=3)
        assert result == set()  # all are noise

    def test_five_runs_threshold(self):
        # threshold = max(2, ceil(5 * 0.5)) = max(2, 3) = 3
        # Must fail in 3+ of 5 runs to be amended
        counts = {"agent-a": 3, "agent-b": 2, "agent-c": 1}
        result = filter_ensemble_failures(counts, total_runs=5)
        assert "agent-a" in result   # 3/5 ≥ 3 — amended
        assert "agent-b" not in result  # 2/5 < 3 — noise
        assert "agent-c" not in result  # 1/5 < 3 — noise

    def test_empty_counts(self):
        result = filter_ensemble_failures({}, total_runs=3)
        assert result == set()


# ── Temple Upgrade 3: Accuracy-based amendment ──────────────────────────────

class TestAccuracyAmendment:
    async def test_accurate_agent_not_amended(self):
        """Agent close to actual outcome should not be amended."""
        llm = FakeLLMClient(responses=[])
        agent = make_agent()
        gt = GroundTruthOutcome(aggregate_stance=0.35, confidence="moderate")
        # Agent final stance 0.3, actual 0.35 → error 0.05 < threshold
        amended = await amend_agent_accuracy(agent, 0.3, gt, make_tick_pairs(), llm)
        assert amended is agent
        assert len(llm.calls) == 0

    async def test_inaccurate_agent_amended(self):
        """Agent far from actual outcome should be amended."""
        llm = FakeLLMClient(responses=[{
            "new_rules": ["Weight macro signals more heavily"],
            "bias_strength_adjustment": "lower",
        }])
        agent = make_agent()
        gt = GroundTruthOutcome(
            aggregate_stance=0.8, confidence="high",
            notes="Strong positive outcome",
        )
        # Agent final stance 0.3, actual 0.8 → error 0.5 > threshold
        amended = await amend_agent_accuracy(agent, 0.3, gt, make_tick_pairs(), llm)
        assert "Weight macro signals more heavily" in amended.behavioral_rules
        assert amended.bias_strength < agent.bias_strength

    async def test_accuracy_prompt_contains_outcome(self):
        """The accuracy prompt should include the actual outcome details."""
        llm = FakeLLMClient(responses=[{
            "new_rules": ["rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        gt = GroundTruthOutcome(
            aggregate_stance=0.8, confidence="high",
            notes="Market rallied 15%",
        )
        await amend_agent_accuracy(agent, 0.3, gt, make_tick_pairs(), llm)
        prompt = llm.calls[0]["prompt"]
        assert "Market rallied 15%" in prompt
        assert "0.80" in prompt  # actual stance
        assert "0.30" in prompt  # agent stance

    async def test_accuracy_respects_rule_cap(self):
        """At rule cap, accuracy amendment only adjusts bias_strength."""
        llm = FakeLLMClient(responses=[{
            "new_rules": ["Should not be added"],
            "bias_strength_adjustment": "raise",
        }])
        agent = make_agent(rule_count=MAX_RULES_PER_AGENT, bias_strength=0.5)
        gt = GroundTruthOutcome(aggregate_stance=0.8, confidence="high")
        amended = await amend_agent_accuracy(agent, 0.3, gt, make_tick_pairs(), llm)
        # Rules unchanged (at cap), but bias_strength adjusted
        assert len(amended.behavioral_rules) == MAX_RULES_PER_AGENT
        assert amended.bias_strength == pytest.approx(0.5 + BIAS_STRENGTH_STEP)

    async def test_accuracy_direction_in_prompt(self):
        """Prompt should say whether agent was too optimistic or pessimistic."""
        llm = FakeLLMClient(responses=[{
            "new_rules": ["rule"],
            "bias_strength_adjustment": "none",
        }])
        agent = make_agent()
        gt = GroundTruthOutcome(aggregate_stance=0.2, confidence="high")
        # Agent at 0.8, actual at 0.2 → too optimistic
        await amend_agent_accuracy(agent, 0.8, gt, make_tick_pairs(), llm)
        assert "optimistic" in llm.calls[0]["prompt"].lower()


# ── Named constants ─────────────────────────────────────────────────────────

class TestNamedConstants:
    def test_max_rules_reasonable(self):
        assert 4 <= MAX_RULES_PER_AGENT <= 12

    def test_ensemble_threshold_is_majority(self):
        assert 0.0 < ENSEMBLE_MAJORITY_THRESHOLD <= 1.0

    def test_accuracy_threshold_reasonable(self):
        assert 0.0 < ACCURACY_AMENDMENT_THRESHOLD <= 0.5

    def test_bias_step_reasonable(self):
        assert 0.0 < BIAS_STRENGTH_STEP <= 0.3
