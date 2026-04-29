"""Tests for the Decision Summary generator."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.confidence import compute_confidence
from pythia.decision import generate_decision_summary, _build_decision_prompt
from pythia.models import (
    DecisionSummary, InfluenceGraph, RunResult, RunSummary,
    ScenarioInfo, AgentInfo, TickRecord, TickEvent, BiggestShift,
)


def make_run_result():
    return RunResult(
        run_id="run_test",
        scenario=ScenarioInfo(
            input="Should we raise a Series A?",
            type="strategic_decision",
            title="Series A Fundraising Decision",
            stance_spectrum=["strongly against", "against", "neutral", "for", "strongly for"],
        ),
        agents=[
            AgentInfo(id="a1", name="Optimist Olivia", role="investor",
                      persona="Bullish VC", bias="optimism", initial_stance=0.7),
            AgentInfo(id="a2", name="Skeptic Sam", role="advisor",
                      persona="Conservative advisor", bias="loss_aversion", initial_stance=0.3),
        ],
        ticks=[
            TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.75, previous_stance=0.7,
                          action="advocate", emotion="excited",
                          reasoning="Market window is open", message="Raise now!"),
                TickEvent(agent_id="a2", stance=0.28, previous_stance=0.3,
                          action="caution", emotion="worried",
                          reasoning="Burn rate is too high", message="Wait."),
            ], aggregate_stance=0.515),
            TickRecord(tick=2, events=[
                TickEvent(agent_id="a1", stance=0.8, previous_stance=0.75,
                          action="push", emotion="confident",
                          reasoning="Competitors are raising", message="Don't miss out!"),
                TickEvent(agent_id="a2", stance=0.35, previous_stance=0.28,
                          action="reconsider", emotion="uncertain",
                          reasoning="Maybe timing matters more than I thought", message="Hmm."),
            ], aggregate_stance=0.575),
        ],
        summary=RunSummary(
            total_ticks=2, final_aggregate_stance=0.575,
            biggest_shift=BiggestShift(agent_id="a1", from_stance=0.7, to_stance=0.8, reason="Competitors"),
            consensus_reached=False,
        ),
    )


def make_influence_graph():
    graph = InfluenceGraph()
    graph.add_tick_state("a1", 1, 0.75, "advocate", "Market window is open", "excited")
    graph.add_tick_state("a2", 1, 0.28, "caution", "Burn rate is too high", "worried")
    graph.add_tick_state("a1", 2, 0.8, "push", "Competitors are raising", "confident")
    graph.add_tick_state("a2", 2, 0.35, "reconsider", "Maybe timing matters", "uncertain")
    graph.add_influence("a1", "a2", 2, "Don't miss out!", 0.75, 0.28, 0.35)
    return graph


# The LLM no longer picks confidence — only rationale, verdict, arguments, etc.
DECISION_RESPONSE = {
    "verdict": "The panel leans toward raising, but with reservations about timing",
    "confidence_rationale": "The two agents landed far apart (σ=0.23), producing a split panel",
    "arguments_for": [
        {"agent_name": "Optimist Olivia", "agent_role": "investor",
         "position": "Raise now", "reasoning": "Market window and competitive pressure"},
    ],
    "arguments_against": [
        {"agent_name": "Skeptic Sam", "agent_role": "advisor",
         "position": "Wait", "reasoning": "Burn rate risk not addressed"},
    ],
    "key_risk": "High burn rate could make the raise a bridge to nowhere",
    "what_could_change": "If burn rate were reduced by 30%, the conservative advisor would likely shift to support",
    "influence_narrative": "Olivia's competitive pressure argument partially moved Sam, but his core concern about burn rate remained unaddressed.",
    "herd_moments": [],
}


class TestGenerateDecisionSummary:
    async def test_returns_valid_decision_summary(self):
        llm = FakeLLMClient(responses=[DECISION_RESPONSE])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        assert isinstance(summary, DecisionSummary)
        assert "raising" in summary.verdict.lower() or "lean" in summary.verdict.lower()

    async def test_confidence_is_computed_deterministically_not_from_llm(self):
        """Confidence label comes from stance dispersion, not LLM output."""
        # Stances end at 0.80 and 0.35 → σ≈0.225 (spread), aggregate 0.575,
        # |agg − 0.5| = 0.075 (tepid) → combined "low"
        llm = FakeLLMClient(responses=[DECISION_RESPONSE])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        # Precompute the expected reading and assert the label matches
        expected = compute_confidence([0.80, 0.35])
        assert summary.confidence == expected.label
        assert summary.agreement_label == expected.agreement
        assert summary.conviction_label == expected.conviction
        assert summary.stance_stddev == expected.stance_stddev
        assert summary.stance_spread == expected.stance_spread

    async def test_llm_cannot_override_confidence_label(self):
        """Even if the LLM tries to set confidence, it's ignored."""
        bad_response = {**DECISION_RESPONSE, "confidence": "high"}
        llm = FakeLLMClient(responses=[bad_response])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        # The expected label from dispersion is "low", not "high"
        expected = compute_confidence([0.80, 0.35])
        assert summary.confidence == expected.label
        assert summary.confidence != "high"

    async def test_arguments_parsed_correctly(self):
        llm = FakeLLMClient(responses=[DECISION_RESPONSE])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        assert len(summary.arguments_for) == 1
        assert summary.arguments_for[0].agent_name == "Optimist Olivia"
        assert len(summary.arguments_against) == 1

    async def test_handles_empty_llm_response_gracefully(self):
        llm = FakeLLMClient(responses=[{}])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        assert isinstance(summary, DecisionSummary)
        # Confidence still computed from dispersion even when LLM returns nothing
        expected = compute_confidence([0.80, 0.35])
        assert summary.confidence == expected.label
        assert summary.arguments_for == []
        # Rationale falls back to the deterministic description
        assert summary.confidence_rationale  # non-empty

    async def test_verdict_stance_matches_aggregate(self):
        llm = FakeLLMClient(responses=[DECISION_RESPONSE])
        result = make_run_result()
        graph = make_influence_graph()

        summary = await generate_decision_summary(result, graph, llm)

        assert summary.verdict_stance == result.summary.final_aggregate_stance


class TestBuildDecisionPrompt:
    def test_prompt_contains_user_question(self):
        result = make_run_result()
        graph = make_influence_graph()
        reading = compute_confidence([0.80, 0.35])
        prompt = _build_decision_prompt(result, graph, reading)
        assert "Should we raise a Series A?" in prompt

    def test_prompt_contains_agent_trajectories(self):
        result = make_run_result()
        graph = make_influence_graph()
        reading = compute_confidence([0.80, 0.35])
        prompt = _build_decision_prompt(result, graph, reading)
        assert "Optimist Olivia" in prompt
        assert "Skeptic Sam" in prompt

    def test_prompt_contains_influence_events(self):
        result = make_run_result()
        graph = make_influence_graph()
        reading = compute_confidence([0.80, 0.35])
        prompt = _build_decision_prompt(result, graph, reading)
        assert "Don't miss out!" in prompt

    def test_prompt_includes_computed_confidence_label(self):
        """LLM must see the deterministic confidence label so its rationale aligns with it."""
        result = make_run_result()
        graph = make_influence_graph()
        reading = compute_confidence([0.80, 0.35])
        prompt = _build_decision_prompt(result, graph, reading)
        assert "COMPUTED CONFIDENCE" in prompt
        assert reading.label in prompt

    def test_prompt_works_with_empty_graph(self):
        result = make_run_result()
        graph = InfluenceGraph()
        reading = compute_confidence([0.80, 0.35])
        prompt = _build_decision_prompt(result, graph, reading)
        assert "Should we raise a Series A?" in prompt
