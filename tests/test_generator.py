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



class TestDedupeAgentIds:
    def test_unique_ids_unchanged(self):
        from pythia.generator import _dedupe_agent_ids
        agents = [
            Agent(id="a", name="A", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="b", name="B", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
        ]
        out = _dedupe_agent_ids(agents)
        assert [a.id for a in out] == ["a", "b"]

    def test_duplicate_ids_get_numeric_suffix(self):
        from pythia.generator import _dedupe_agent_ids
        agents = [
            Agent(id="analyst-marcus", name="Bullish Marcus", role="analyst",
                  persona="p", bias="recency_bias", initial_stance=0.85,
                  behavioral_rules=["x"]),
            Agent(id="analyst-marcus", name="Skeptical Marcus", role="analyst",
                  persona="p", bias="negativity_bias", initial_stance=0.25,
                  behavioral_rules=["x"]),
            Agent(id="analyst-marcus", name="Third Marcus", role="analyst",
                  persona="p", bias="anchoring", initial_stance=0.5,
                  behavioral_rules=["x"]),
        ]
        out = _dedupe_agent_ids(agents)
        ids = [a.id for a in out]
        assert ids[0] == "analyst-marcus"        # first occurrence keeps id
        assert ids[1] == "analyst-marcus-2"
        assert ids[2] == "analyst-marcus-3"
        # Names are untouched — name dedupe runs separately
        assert out[0].name == "Bullish Marcus"

    def test_suffix_collides_with_existing_id(self):
        from pythia.generator import _dedupe_agent_ids
        agents = [
            Agent(id="x", name="X1", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="x-2", name="X2", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="x", name="X3", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
        ]
        out = _dedupe_agent_ids(agents)
        ids = [a.id for a in out]
        # First x keeps id, second (x-2) keeps id, third must skip to x-3
        assert ids == ["x", "x-2", "x-3"]


class TestEnsureModerateVoice:
    """The panel should have at least one voice in [0.4, 0.6] when split."""

    def test_already_has_moderate_no_change(self):
        from pythia.generator import _ensure_moderate_voice
        agents = [
            Agent(id="a1", name="A1", role="r", persona="p", bias="anchoring",
                  initial_stance=0.1, behavioral_rules=["x"]),
            Agent(id="a2", name="A2", role="r", persona="p", bias="anchoring",
                  initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="a3", name="A3", role="r", persona="p", bias="anchoring",
                  initial_stance=0.9, behavioral_rules=["x"]),
        ]
        out = _ensure_moderate_voice(agents)
        assert [a.initial_stance for a in out] == [0.1, 0.5, 0.9]

    def test_u_shaped_panel_promotes_nearest_to_moderate(self):
        from pythia.generator import _ensure_moderate_voice
        # U-shaped Netflix-like panel: 4 extreme-con, 3 extreme-pro, no middle.
        agents = [
            Agent(id=f"a{i}", name=f"A{i}", role="r", persona="p",
                  bias="anchoring", initial_stance=s, behavioral_rules=["x"])
            for i, s in enumerate([0.15, 0.2, 0.22, 0.25, 0.85, 0.88, 0.92])
        ]
        out = _ensure_moderate_voice(agents)
        # Exactly one agent should now sit in [0.4, 0.6]
        moderates = [a for a in out if 0.4 <= a.initial_stance <= 0.6]
        assert len(moderates) == 1
        # The promoted agent should be the one who started closest to 0.5 (0.25)
        assert moderates[0].id == "a3"
        # Everyone else is untouched — no panel-wide shift
        unchanged = [a for a in out if a.id != "a3"]
        orig = [0.15, 0.2, 0.22, 0.85, 0.88, 0.92]
        assert sorted(a.initial_stance for a in unchanged) == orig

    def test_not_u_shaped_no_change(self):
        from pythia.generator import _ensure_moderate_voice
        # Skewed-pro panel but not U-shaped: only 1 con voice.
        agents = [
            Agent(id=f"a{i}", name=f"A{i}", role="r", persona="p",
                  bias="anchoring", initial_stance=s, behavioral_rules=["x"])
            for i, s in enumerate([0.2, 0.7, 0.8, 0.9])
        ]
        out = _ensure_moderate_voice(agents)
        assert [a.initial_stance for a in out] == [0.2, 0.7, 0.8, 0.9]

    def test_small_panel_unchanged(self):
        from pythia.generator import _ensure_moderate_voice
        agents = [
            Agent(id="a", name="A", role="r", persona="p", bias="anchoring",
                  initial_stance=0.1, behavioral_rules=["x"]),
            Agent(id="b", name="B", role="r", persona="p", bias="anchoring",
                  initial_stance=0.9, behavioral_rules=["x"]),
        ]
        out = _ensure_moderate_voice(agents)
        assert [a.initial_stance for a in out] == [0.1, 0.9]


class TestBiasImbalance:
    def test_neutral_panel_zero_score(self):
        from pythia.generator import _bias_imbalance
        agents = [
            Agent(id="a", name="A", role="r", persona="p", bias="anchoring",
                  bias_strength=0.8, initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="b", name="B", role="r", persona="p", bias="confirmation_bias",
                  bias_strength=0.7, initial_stance=0.5, behavioral_rules=["x"]),
        ]
        assert _bias_imbalance(agents) == 0.0

    def test_negativity_skew(self):
        from pythia.generator import _bias_imbalance
        agents = [
            Agent(id="a", name="A", role="r", persona="p", bias="negativity_bias",
                  bias_strength=0.7, initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="b", name="B", role="r", persona="p", bias="anchoring",
                  bias_strength=0.5, initial_stance=0.5, behavioral_rules=["x"]),
        ]
        # One negativity bias at 0.7 strength, no optimism — score = -0.7
        assert _bias_imbalance(agents) == -0.7

    def test_paired_biases_cancel(self):
        from pythia.generator import _bias_imbalance
        agents = [
            Agent(id="a", name="A", role="r", persona="p", bias="negativity_bias",
                  bias_strength=0.7, initial_stance=0.5, behavioral_rules=["x"]),
            Agent(id="b", name="B", role="r", persona="p", bias="optimism_bias",
                  bias_strength=0.7, initial_stance=0.5, behavioral_rules=["x"]),
        ]
        assert _bias_imbalance(agents) == 0.0
