"""Tests for the Decision Summary generator."""

import pytest
from tests.conftest import FakeLLMClient
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


DECISION_RESPONSE = {
    "verdict": "The panel leans toward raising, but with reservations about timing",
    "confidence": "moderate",
    "confidence_rationale": "One agent shifted toward raising but the dissenter's concern about burn rate was not fully addressed",
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
        assert summary.confidence == "moderate"

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
        assert summary.confidence == "low"
        assert summary.arguments_for == []

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
        prompt = _build_decision_prompt(result, graph)
        assert "Should we raise a Series A?" in prompt

    def test_prompt_contains_agent_trajectories(self):
        result = make_run_result()
        graph = make_influence_graph()
        prompt = _build_decision_prompt(result, graph)
        assert "Optimist Olivia" in prompt
        assert "Skeptic Sam" in prompt

    def test_prompt_contains_influence_events(self):
        result = make_run_result()
        graph = make_influence_graph()
        prompt = _build_decision_prompt(result, graph)
        assert "Don't miss out!" in prompt

    def test_prompt_works_with_empty_graph(self):
        result = make_run_result()
        graph = InfluenceGraph()
        prompt = _build_decision_prompt(result, graph)
        assert "Should we raise a Series A?" in prompt
