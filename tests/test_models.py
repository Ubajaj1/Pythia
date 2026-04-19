"""Tests for Pythia data models."""

import pytest
from pydantic import ValidationError
from pythia.models import (
    AgentArchetype,
    ScenarioBlueprint,
    Agent,
    Relationship,
    TickAction,
    TickEvent,
    TickRecord,
    RunResult,
    RunSummary,
    SimulateRequest,
    AgentEvaluation,
    OracleRunRecord,
    OracleLoopResult,
    OracleRequest,
    ScenarioInfo,
    AgentInfo,
    BiggestShift,
)


class TestAgentArchetype:
    def test_valid_archetype(self):
        a = AgentArchetype(
            role="retail_investor",
            count=2,
            description="Individual investors",
            bias="loss_aversion",
            stance_range=(0.2, 0.4),
        )
        assert a.role == "retail_investor"
        assert a.count == 2
        assert a.stance_range == (0.2, 0.4)

    def test_stance_range_must_be_0_to_1(self):
        with pytest.raises(ValidationError):
            AgentArchetype(
                role="x", count=1, description="x",
                bias="x", stance_range=(-0.1, 0.5),
            )

    def test_stance_range_low_must_be_less_than_high(self):
        with pytest.raises(ValidationError):
            AgentArchetype(
                role="x", count=1, description="x",
                bias="x", stance_range=(0.8, 0.2),
            )


class TestScenarioBlueprint:
    def test_valid_blueprint(self):
        bp = ScenarioBlueprint(
            scenario_type="market_event",
            title="Fed Rate Hike",
            description="Rate hike simulation",
            stance_spectrum=["very bearish", "bearish", "neutral", "bullish", "very bullish"],
            agent_archetypes=[
                AgentArchetype(role="retail", count=2, description="d", bias="loss_aversion", stance_range=(0.2, 0.4)),
            ],
            dynamics="Herd behavior likely.",
            tick_count=20,
        )
        assert bp.scenario_type == "market_event"
        assert len(bp.stance_spectrum) == 5

    def test_stance_spectrum_must_have_5_labels(self):
        with pytest.raises(ValidationError):
            ScenarioBlueprint(
                scenario_type="x", title="x", description="x",
                stance_spectrum=["a", "b", "c"],
                agent_archetypes=[], dynamics="x", tick_count=20,
            )


class TestAgent:
    def test_valid_agent(self):
        a = Agent(
            id="retail-rachel",
            name="Retail Rachel",
            role="retail_investor",
            persona="A 34-year-old trader.",
            bias="loss_aversion",
            initial_stance=0.35,
            behavioral_rules=["Sells quickly when negative"],
            relationships=[],
        )
        assert a.id == "retail-rachel"
        assert a.initial_stance == 0.35

    def test_stance_clamped_to_0_1(self):
        with pytest.raises(ValidationError):
            Agent(
                id="x", name="x", role="x", persona="x",
                bias="x", initial_stance=1.5,
                behavioral_rules=[], relationships=[],
            )


class TestTickAction:
    def test_valid_action(self):
        ta = TickAction(
            stance=0.25,
            action="sell",
            emotion="panicking",
            reasoning="Everyone is dumping",
            message="I'm out.",
            influence_target="elias",
        )
        assert ta.stance == 0.25

    def test_stance_clamped(self):
        ta = TickAction(
            stance=1.8, action="buy", emotion="manic",
            reasoning="x", message="x", influence_target=None,
        )
        assert ta.stance == 1.0

    def test_negative_stance_clamped(self):
        ta = TickAction(
            stance=-0.3, action="sell", emotion="fear",
            reasoning="x", message="x", influence_target=None,
        )
        assert ta.stance == 0.0


class TestRunResult:
    def test_valid_run_result(self):
        result = RunResult(
            run_id="run_2026-04-04_001",
            scenario={
                "input": "Fed raises rates",
                "type": "market_event",
                "title": "Fed Rate Hike",
                "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
            },
            agents=[],
            ticks=[],
            summary=RunSummary(
                total_ticks=20,
                final_aggregate_stance=0.58,
                biggest_shift={"agent_id": "rachel", "from_stance": 0.35, "to_stance": 0.72, "reason": "x"},
                consensus_reached=False,
            ),
        )
        assert result.run_id == "run_2026-04-04_001"


class TestSimulateRequest:
    def test_valid_request(self):
        r = SimulateRequest(prompt="Fed raises rates 50bps")
        assert r.prompt == "Fed raises rates 50bps"
        assert r.context is None

    def test_with_context(self):
        r = SimulateRequest(prompt="Buy or rent?", context="I have 50k saved")
        assert r.context == "I have 50k saved"


class TestAgentEvaluation:
    def test_coherent_evaluation(self):
        e = AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None)
        assert e.agent_id == "a1"
        assert e.is_coherent is True
        assert e.incoherence_summary is None

    def test_incoherent_evaluation_requires_summary(self):
        e = AgentEvaluation(
            agent_id="a1", is_coherent=False,
            incoherence_summary="Agent said sell but stance increased",
        )
        assert e.is_coherent is False
        assert e.incoherence_summary is not None


class TestOracleRequest:
    def test_defaults(self):
        req = OracleRequest(prompt="Test")
        assert req.max_runs == 5
        assert req.context is None

    def test_max_runs_validation(self):
        import pytest
        with pytest.raises(Exception):
            OracleRequest(prompt="Test", max_runs=0)
        with pytest.raises(Exception):
            OracleRequest(prompt="Test", max_runs=11)


class TestOracleLoopResult:
    def _make_run_result(self):
        return RunResult(
            run_id="r1",
            scenario=ScenarioInfo(input="t", type="m", title="T", stance_spectrum=["a","b","c","d","e"]),
            agents=[AgentInfo(id="a1", name="A", role="r", persona="p", bias="b", initial_stance=0.5)],
            ticks=[TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.5, previous_stance=0.5, action="hold", emotion="calm", reasoning="ok", message="ok"),
            ], aggregate_stance=0.5)],
            summary=RunSummary(
                total_ticks=1, final_aggregate_stance=0.5,
                biggest_shift=BiggestShift(agent_id="a1", from_stance=0.5, to_stance=0.5, reason=""),
                consensus_reached=True,
            ),
        )

    def test_coherence_history_matches_runs_length(self):
        run_record = OracleRunRecord(
            run_number=1,
            result=self._make_run_result(),
            evaluations=[AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None)],
            coherence_score=1.0,
            amended_agent_ids=[],
        )
        result = OracleLoopResult(
            prompt="test",
            runs=[run_record],
            coherence_history=[1.0],
        )
        assert len(result.coherence_history) == len(result.runs)
