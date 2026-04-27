"""Tests for the shared summary computation module."""

import pytest
from pythia.summary import compute_summary, generate_run_id, build_run_result
from pythia.models import (
    Agent, AgentInfo, TickRecord, TickEvent, RunResult,
    ScenarioBlueprint, AgentArchetype,
)


def make_agents():
    return [
        Agent(
            id="a1", name="Agent A", role="trader", persona="p",
            bias="loss_aversion", initial_stance=0.3,
            behavioral_rules=["rule1"],
        ),
        Agent(
            id="a2", name="Agent B", role="analyst", persona="p",
            bias="anchoring", initial_stance=0.7,
            behavioral_rules=["rule2"],
        ),
    ]


def make_ticks():
    return [
        TickRecord(tick=1, events=[
            TickEvent(agent_id="a1", stance=0.25, previous_stance=0.3,
                      action="sell", emotion="anxious", reasoning="bad", message="m"),
            TickEvent(agent_id="a2", stance=0.72, previous_stance=0.7,
                      action="hold", emotion="calm", reasoning="ok", message="m"),
        ], aggregate_stance=0.485),
        TickRecord(tick=2, events=[
            TickEvent(agent_id="a1", stance=0.2, previous_stance=0.25,
                      action="sell more", emotion="panic", reasoning="worse", message="m"),
            TickEvent(agent_id="a2", stance=0.75, previous_stance=0.72,
                      action="buy", emotion="confident", reasoning="opportunity", message="m"),
        ], aggregate_stance=0.475),
    ]


def make_blueprint():
    return ScenarioBlueprint(
        scenario_type="market_event", title="Test", description="Test sim",
        stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        agent_archetypes=[
            AgentArchetype(role="trader", count=1, description="d",
                           bias="loss_aversion", stance_range=(0.2, 0.4)),
        ],
        dynamics="Test dynamics", tick_count=2,
    )


class TestGenerateRunId:
    def test_contains_prefix(self):
        rid = generate_run_id("run")
        assert rid.startswith("run_")

    def test_custom_prefix(self):
        rid = generate_run_id("oracle")
        assert rid.startswith("oracle_")

    def test_no_collision(self):
        """Two IDs generated in the same second should differ (UUID suffix)."""
        ids = {generate_run_id() for _ in range(100)}
        assert len(ids) == 100

    def test_format(self):
        rid = generate_run_id()
        # Should be like: run_2026-04-27_004500_a1b2c3
        parts = rid.split("_")
        assert len(parts) == 4  # prefix, date, time, uuid


class TestComputeSummary:
    def test_correct_tick_count(self):
        summary = compute_summary(make_ticks(), make_agents())
        assert summary.total_ticks == 2

    def test_final_aggregate_from_last_tick(self):
        summary = compute_summary(make_ticks(), make_agents())
        assert summary.final_aggregate_stance == 0.475

    def test_biggest_shift_identified(self):
        summary = compute_summary(make_ticks(), make_agents())
        # a1: 0.3 → 0.2 = 0.1 shift, a2: 0.7 → 0.75 = 0.05 shift
        assert summary.biggest_shift.agent_id == "a1"

    def test_consensus_false_when_spread(self):
        summary = compute_summary(make_ticks(), make_agents())
        # 0.2 and 0.75 are 0.55 apart — no consensus
        assert summary.consensus_reached is False

    def test_consensus_true_when_close(self):
        close_ticks = [
            TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.5, previous_stance=0.3,
                          action="hold", emotion="calm", reasoning="ok", message="m"),
                TickEvent(agent_id="a2", stance=0.55, previous_stance=0.7,
                          action="hold", emotion="calm", reasoning="ok", message="m"),
            ], aggregate_stance=0.525),
        ]
        summary = compute_summary(close_ticks, make_agents())
        assert summary.consensus_reached is True

    def test_works_with_agent_info_objects(self):
        """Should work with AgentInfo (from results) not just Agent (from generator)."""
        agent_infos = [
            AgentInfo(id="a1", name="A", role="r", persona="p", bias="b", initial_stance=0.3),
            AgentInfo(id="a2", name="B", role="r", persona="p", bias="b", initial_stance=0.7),
        ]
        summary = compute_summary(make_ticks(), agent_infos)
        assert summary.total_ticks == 2


class TestBuildRunResult:
    def test_returns_valid_run_result(self):
        result = build_run_result("test prompt", make_blueprint(), make_agents(), make_ticks())
        assert isinstance(result, RunResult)
        assert result.scenario.title == "Test"
        assert len(result.agents) == 2
        assert len(result.ticks) == 2

    def test_custom_run_id(self):
        result = build_run_result("test", make_blueprint(), make_agents(), make_ticks(),
                                  run_id="custom_id_123")
        assert result.run_id == "custom_id_123"

    def test_auto_generates_run_id(self):
        result = build_run_result("test", make_blueprint(), make_agents(), make_ticks())
        assert result.run_id.startswith("run_")
