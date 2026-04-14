"""Tests for the Scenario Analyzer."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.analyzer import analyze_scenario
from pythia.models import ScenarioBlueprint


MARKET_BLUEPRINT_RESPONSE = {
    "scenario_type": "market_event",
    "title": "Federal Reserve 50bps Rate Hike",
    "description": "Simulation of market reactions to rate increase",
    "stance_spectrum": ["very bearish", "bearish", "neutral", "bullish", "very bullish"],
    "agent_archetypes": [
        {"role": "retail_investor", "count": 2, "description": "Individual investors", "bias": "loss_aversion", "stance_range": [0.2, 0.4]},
        {"role": "institutional_investor", "count": 2, "description": "Fund managers", "bias": "anchoring", "stance_range": [0.5, 0.8]},
        {"role": "market_analyst", "count": 1, "description": "Analyst", "bias": "confirmation", "stance_range": [0.4, 0.6]},
    ],
    "dynamics": "Herd behavior likely among retail investors.",
    "tick_count": 20,
}

PERSONAL_BLUEPRINT_RESPONSE = {
    "scenario_type": "personal_decision",
    "title": "Buy vs Rent in Austin",
    "description": "Advisors and peers weigh in on housing decision",
    "stance_spectrum": ["strongly rent", "lean rent", "undecided", "lean buy", "strongly buy"],
    "agent_archetypes": [
        {"role": "financial_advisor", "count": 1, "description": "Conservative planner", "bias": "anchoring", "stance_range": [0.3, 0.5]},
        {"role": "homeowner_peer", "count": 2, "description": "Friends who bought", "bias": "confirmation", "stance_range": [0.6, 0.9]},
        {"role": "renter_peer", "count": 2, "description": "Friends who rent and invest", "bias": "status_quo", "stance_range": [0.1, 0.4]},
    ],
    "dynamics": "Peers share personal experiences. Advisor provides data-driven analysis.",
    "tick_count": 20,
}


class TestAnalyzeScenario:
    async def test_returns_valid_blueprint_for_market_event(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        result = await analyze_scenario("Fed raises rates 50bps", llm=llm)
        assert isinstance(result, ScenarioBlueprint)
        assert result.scenario_type == "market_event"
        assert len(result.agent_archetypes) == 3
        assert result.tick_count == 20

    async def test_returns_valid_blueprint_for_personal_decision(self):
        llm = FakeLLMClient(responses=[PERSONAL_BLUEPRINT_RESPONSE])
        result = await analyze_scenario("Should I buy or rent in Austin?", llm=llm)
        assert isinstance(result, ScenarioBlueprint)
        assert result.scenario_type == "personal_decision"
        assert result.stance_spectrum[0] == "strongly rent"

    async def test_passes_context_in_prompt(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates", context="Market is volatile", llm=llm)
        prompt_sent = llm.calls[0]["prompt"]
        assert "Market is volatile" in prompt_sent

    async def test_prompt_includes_user_input(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates 50bps", llm=llm)
        prompt_sent = llm.calls[0]["prompt"]
        assert "Fed raises rates 50bps" in prompt_sent

    async def test_system_prompt_describes_analyzer_role(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates", llm=llm)
        system_sent = llm.calls[0]["system"]
        assert system_sent is not None
        assert "scenario" in system_sent.lower()
