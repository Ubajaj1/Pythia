"""Tests for the Agent Generator."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.generator import generate_agents
from pythia.models import AgentArchetype, ScenarioBlueprint, Agent


def make_blueprint(**overrides) -> ScenarioBlueprint:
    defaults = {
        "scenario_type": "market_event",
        "title": "Test Scenario",
        "description": "A test",
        "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
        "agent_archetypes": [
            AgentArchetype(role="retail", count=1, description="Retail trader", bias="loss_aversion", stance_range=(0.2, 0.4)),
            AgentArchetype(role="institutional", count=1, description="Fund manager", bias="anchoring", stance_range=(0.6, 0.8)),
        ],
        "dynamics": "Test dynamics",
        "tick_count": 20,
    }
    defaults.update(overrides)
    return ScenarioBlueprint(**defaults)


# Pass 1 response: one agent per archetype (no relationships)
# Stances are 0.2 and 0.8 — spread of 0.6, which exactly meets min_spread,
# so the diversity check does NOT trigger an extra call.
PASS1_RETAIL = {
    "agents": [
        {
            "id": "retail-rachel",
            "name": "Retail Rachel",
            "role": "retail",
            "persona": "34-year-old self-taught trader.",
            "bias": "loss_aversion",
            "initial_stance": 0.2,
            "behavioral_rules": ["Sells on bad news", "Follows social media"],
        }
    ]
}

PASS1_INSTITUTIONAL = {
    "agents": [
        {
            "id": "institutional-ivan",
            "name": "Institutional Ivan",
            "role": "institutional",
            "persona": "Veteran fund manager, 20 years experience.",
            "bias": "anchoring",
            "initial_stance": 0.8,
            "behavioral_rules": ["Holds through volatility", "Anchors to fundamentals"],
        }
    ]
}

# Pass 2 response: relationships for all agents
PASS2_RELATIONSHIPS = {
    "relationships": {
        "retail-rachel": [
            {"target": "institutional-ivan", "type": "distrusts", "weight": 0.7}
        ],
        "institutional-ivan": [
            {"target": "retail-rachel", "type": "respects", "weight": 0.3}
        ],
    }
}


class TestGenerateAgents:
    async def test_returns_correct_number_of_agents(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        assert len(agents) == 2

    async def test_agents_have_valid_structure(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        for agent in agents:
            assert isinstance(agent, Agent)
            assert agent.id
            assert agent.name
            assert agent.persona
            assert len(agent.behavioral_rules) > 0

    async def test_relationships_assigned_from_pass2(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        rachel = next(a for a in agents if a.id == "retail-rachel")
        assert len(rachel.relationships) == 1
        assert rachel.relationships[0].target == "institutional-ivan"

    async def test_pass1_calls_equal_archetype_count(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        await generate_agents(bp, llm=llm)
        # 2 archetypes = 2 pass1 calls + 1 pass2 call = 3 total
        # Stances are 0.2 and 0.8 (spread = 0.6), so diversity check does NOT fire.
        assert len(llm.calls) == 3

    async def test_diversity_check_passes_with_spread_stances(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        stances = [a.initial_stance for a in agents]
        spread = max(stances) - min(stances)
        assert spread >= 0.3  # 0.8 - 0.2 = 0.6
