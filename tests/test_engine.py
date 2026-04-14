"""Tests for the Simulation Engine."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.engine import SimulationEngine, AgentMemory
from pythia.models import Agent, Relationship, ScenarioBlueprint, AgentArchetype, TickRecord


def make_test_agents() -> list[Agent]:
    return [
        Agent(
            id="agent-a", name="Agent A", role="trader", persona="Cautious trader.",
            bias="loss_aversion", initial_stance=0.3,
            behavioral_rules=["Sells on bad news"],
            relationships=[Relationship(target="agent-b", type="follows", weight=0.5)],
        ),
        Agent(
            id="agent-b", name="Agent B", role="analyst", persona="Data-driven analyst.",
            bias="anchoring", initial_stance=0.7,
            behavioral_rules=["Holds to fundamentals"],
            relationships=[Relationship(target="agent-a", type="respects", weight=0.3)],
        ),
    ]


def make_test_blueprint() -> ScenarioBlueprint:
    return ScenarioBlueprint(
        scenario_type="market_event", title="Test", description="Test sim",
        stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        agent_archetypes=[
            AgentArchetype(role="trader", count=1, description="d", bias="loss_aversion", stance_range=(0.2, 0.4)),
        ],
        dynamics="Test dynamics", tick_count=3,
    )


TICK_RESPONSE_A = {
    "stance": 0.25,
    "action": "sell",
    "emotion": "anxious",
    "reasoning": "Bad signals from the market",
    "message": "I'm reducing my position.",
    "influence_target": "agent-b",
}

TICK_RESPONSE_B = {
    "stance": 0.68,
    "action": "hold",
    "emotion": "steady",
    "reasoning": "Fundamentals unchanged",
    "message": "Staying the course.",
    "influence_target": "agent-a",
}


class TestAgentMemory:
    def test_starts_empty(self):
        mem = AgentMemory("agent-a")
        assert mem.for_prompt() == []

    def test_records_and_retrieves(self):
        mem = AgentMemory("agent-a")
        mem.record({"tick": 1, "stance": 0.3})
        mem.record({"tick": 2, "stance": 0.25})
        assert len(mem.for_prompt()) == 2
        assert mem.for_prompt()[0]["tick"] == 1


class TestSimulationEngine:
    async def test_run_produces_correct_tick_count(self):
        # 3 ticks × 2 agents = 6 LLM calls
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        assert len(ticks) == 3

    async def test_each_tick_has_events_for_all_agents(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        for tick in ticks:
            assert isinstance(tick, TickRecord)
            assert len(tick.events) == 2

    async def test_tick_events_have_correct_agent_ids(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        agent_ids = {e.agent_id for e in ticks[0].events}
        assert agent_ids == {"agent-a", "agent-b"}

    async def test_aggregate_stance_is_average(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        # (0.25 + 0.68) / 2 = 0.465
        assert abs(ticks[0].aggregate_stance - 0.465) < 0.01

    async def test_previous_stance_tracks_correctly(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        # Tick 1: previous stance should be initial stance
        event_a_tick1 = next(e for e in ticks[0].events if e.agent_id == "agent-a")
        assert event_a_tick1.previous_stance == 0.3
        # Tick 2: previous stance should be tick 1's stance
        event_a_tick2 = next(e for e in ticks[1].events if e.agent_id == "agent-a")
        assert event_a_tick2.previous_stance == 0.25

    async def test_memory_grows_across_ticks(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        await engine.run()
        # After 3 ticks, each agent's memory should have 3 entries
        assert len(engine.memories["agent-a"].for_prompt()) == 3
        assert len(engine.memories["agent-b"].for_prompt()) == 3
