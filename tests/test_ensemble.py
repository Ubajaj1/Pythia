"""Tests for ensemble runs — Step 6."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.ensemble import (
    _aggregate_ensemble,
    run_ensemble,
    DEFAULT_ENSEMBLE_SIZE,
    ROBUST_HERD_MOMENT_THRESHOLD,
    ENSEMBLE_AGREEMENT_THRESHOLD,
)
from pythia.models import (
    AgentInfo,
    BiggestShift,
    DecisionSummary,
    EnsembleResult,
    InfluenceGraph,
    KeyArgument,
    RunResultWithInsights,
    RunSummary,
    ScenarioInfo,
    TickEvent,
    TickRecord,
)


def _make_run(
    run_id: str,
    final_aggregate: float,
    confidence: str,
    herd_moments: list[str] | None = None,
) -> RunResultWithInsights:
    """Build a minimal RunResultWithInsights for testing aggregation."""
    return RunResultWithInsights(
        run_id=run_id,
        scenario=ScenarioInfo(
            input="test", type="test", title="Test",
            stance_spectrum=["a", "b", "c", "d", "e"],
        ),
        agents=[
            AgentInfo(id="a1", name="A1", role="r", persona="p",
                      bias="anchoring", initial_stance=0.5),
        ],
        ticks=[
            TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=final_aggregate,
                          previous_stance=0.5, action="a", emotion="e",
                          reasoning="r", message="m"),
            ], aggregate_stance=final_aggregate),
        ],
        summary=RunSummary(
            total_ticks=1,
            final_aggregate_stance=final_aggregate,
            biggest_shift=BiggestShift(
                agent_id="a1", from_stance=0.5,
                to_stance=final_aggregate, reason="test",
            ),
            consensus_reached=True,
        ),
        influence_graph=InfluenceGraph(),
        decision_summary=DecisionSummary(
            verdict="test",
            verdict_stance=final_aggregate,
            confidence=confidence,
            confidence_rationale="test",
            arguments_for=[],
            arguments_against=[],
            key_risk="test",
            what_could_change="test",
            influence_narrative="test",
            herd_moments=herd_moments or [],
        ),
    )


class TestAggregateEnsemble:
    """Tests for the pure aggregation function."""

    def test_empty_runs(self):
        result = _aggregate_ensemble([])
        assert result["aggregate_distribution"] == []
        assert result["agreement_ratio"] == 0.0
        assert result["ensemble_confidence"] == "low"

    def test_single_run(self):
        runs = [_make_run("r1", 0.7, "high")]
        result = _aggregate_ensemble(runs)
        assert result["aggregate_distribution"] == [0.7]
        assert result["confidence_distribution"] == ["high"]
        assert result["agreement_ratio"] == 1.0
        assert result["ensemble_confidence"] == "high"

    def test_three_runs_unanimous(self):
        runs = [
            _make_run("r1", 0.7, "high"),
            _make_run("r2", 0.72, "high"),
            _make_run("r3", 0.68, "high"),
        ]
        result = _aggregate_ensemble(runs)
        assert len(result["aggregate_distribution"]) == 3
        assert result["agreement_ratio"] == 1.0
        assert result["ensemble_confidence"] == "high"

    def test_three_runs_majority(self):
        runs = [
            _make_run("r1", 0.7, "high"),
            _make_run("r2", 0.72, "high"),
            _make_run("r3", 0.45, "moderate"),
        ]
        result = _aggregate_ensemble(runs)
        # 2/3 agree on "high" → agreement_ratio = 0.6667
        assert result["agreement_ratio"] == pytest.approx(0.6667, abs=0.001)
        # 0.6667 >= ENSEMBLE_AGREEMENT_THRESHOLD (0.6) → consensus is "high"
        assert result["ensemble_confidence"] == "high"

    def test_three_runs_no_agreement(self):
        runs = [
            _make_run("r1", 0.7, "high"),
            _make_run("r2", 0.45, "moderate"),
            _make_run("r3", 0.5, "low"),
        ]
        result = _aggregate_ensemble(runs)
        # All different → agreement_ratio = 1/3 = 0.3333
        assert result["agreement_ratio"] == pytest.approx(0.3333, abs=0.001)
        # Worst-case confidence: "low" (rank 0)
        assert result["ensemble_confidence"] == "low"

    def test_herd_moments_deduplication(self):
        runs = [
            _make_run("r1", 0.7, "high", herd_moments=["Tick 5: everyone shifted right"]),
            _make_run("r2", 0.72, "high", herd_moments=["Tick 5: everyone shifted right", "Tick 8: groupthink"]),
            _make_run("r3", 0.68, "high", herd_moments=["Tick 8: groupthink"]),
        ]
        result = _aggregate_ensemble(runs)
        # "Tick 5" appears in 2 runs → robust
        # "Tick 8" appears in 2 runs → robust
        assert len(result["robust_herd_moments"]) == 2
        assert len(result["noisy_herd_moments"]) == 0

    def test_herd_moments_noisy(self):
        runs = [
            _make_run("r1", 0.7, "high", herd_moments=["Tick 5: unique to run 1"]),
            _make_run("r2", 0.72, "high", herd_moments=["Tick 8: unique to run 2"]),
            _make_run("r3", 0.68, "high", herd_moments=[]),
        ]
        result = _aggregate_ensemble(runs)
        # Each herd moment appears in only 1 run → noisy
        assert len(result["robust_herd_moments"]) == 0
        assert len(result["noisy_herd_moments"]) == 2

    def test_aggregate_distribution_correct(self):
        runs = [
            _make_run("r1", 0.3, "low"),
            _make_run("r2", 0.7, "high"),
            _make_run("r3", 0.5, "moderate"),
        ]
        result = _aggregate_ensemble(runs)
        assert result["aggregate_distribution"] == [0.3, 0.7, 0.5]


class TestRunEnsemble:
    """Integration tests for the full ensemble pipeline."""

    async def test_produces_correct_number_of_runs(self):
        """Ensemble with N=3 produces three run results."""
        # We need enough LLM responses for:
        # 1 analyzer call + N_archetypes pass1 calls + 1 pass2 call
        # + 3 runs × (ticks × agents) engine calls + 3 decision calls
        # For simplicity, use a generous number of canned responses.
        blueprint_response = {
            "scenario_type": "test",
            "title": "Test Ensemble",
            "description": "Testing ensemble runs",
            "stance_spectrum": ["strongly oppose", "oppose", "neutral", "support", "strongly support"],
            "agent_archetypes": [
                {"role": "analyst", "count": 2, "description": "d",
                 "bias": "anchoring", "stance_range": [0.2, 0.8]},
            ],
            "dynamics": "test",
            "tick_count": 2,
        }
        agents_response = {
            "agents": [
                {"id": "a1", "name": "A1", "role": "analyst", "persona": "p",
                 "bias": "anchoring", "bias_strength": 0.5,
                 "initial_stance": 0.4, "behavioral_rules": ["r1"]},
                {"id": "a2", "name": "A2", "role": "analyst", "persona": "p",
                 "bias": "anchoring", "bias_strength": 0.5,
                 "initial_stance": 0.6, "behavioral_rules": ["r2"]},
            ],
        }
        relationships_response = {"relationships": {}}
        tick_response = {
            "stance": 0.5, "action": "hold", "emotion": "calm",
            "reasoning": "test", "message": "test", "influence_target": None,
        }
        decision_response = {
            "verdict": "test verdict",
            "confidence_rationale": "test rationale",
            "arguments_for": [],
            "arguments_against": [],
            "key_risk": "test risk",
            "what_could_change": "test change",
            "actionable_takeaways": [],
            "influence_narrative": "test narrative",
            "herd_moments": [],
        }

        # 1 blueprint + 1 pass1 + 1 pass2 + 3×(2 ticks × 2 agents) + 3 decisions
        responses = (
            [blueprint_response, agents_response, relationships_response]
            + [tick_response] * (3 * 2 * 2)  # 3 runs × 2 ticks × 2 agents
            + [decision_response] * 3         # 3 decision summaries
        )
        llm = FakeLLMClient(responses=responses)

        result = await run_ensemble(
            prompt="Test ensemble",
            llm=llm,
            ensemble_size=3,
            runs_dir="/tmp/pythia_test_ensemble",
        )

        assert isinstance(result, EnsembleResult)
        assert result.ensemble_size == 3
        assert len(result.runs) == 3
        assert result.primary_run is not None
        assert result.primary_run.run_id == result.runs[0].run_id

    async def test_single_run_fallback(self):
        """Ensemble with N=1 still works — single-run fallback."""
        blueprint_response = {
            "scenario_type": "test",
            "title": "Test",
            "description": "d",
            "stance_spectrum": ["a", "b", "c", "d", "e"],
            "agent_archetypes": [
                {"role": "r", "count": 1, "description": "d",
                 "bias": "anchoring", "stance_range": [0.3, 0.7]},
            ],
            "dynamics": "d",
            "tick_count": 1,
        }
        agents_response = {
            "agents": [
                {"id": "a1", "name": "A1", "role": "r", "persona": "p",
                 "bias": "anchoring", "bias_strength": 0.5,
                 "initial_stance": 0.5, "behavioral_rules": ["r"]},
            ],
        }
        relationships_response = {"relationships": {}}
        tick_response = {
            "stance": 0.6, "action": "a", "emotion": "e",
            "reasoning": "r", "message": "m", "influence_target": None,
        }
        decision_response = {
            "verdict": "v", "confidence_rationale": "cr",
            "arguments_for": [], "arguments_against": [],
            "key_risk": "k", "what_could_change": "w",
            "actionable_takeaways": [], "influence_narrative": "i",
            "herd_moments": [],
        }

        responses = [
            blueprint_response, agents_response, relationships_response,
            tick_response,  # 1 run × 1 tick × 1 agent
            decision_response,
        ]
        llm = FakeLLMClient(responses=responses)

        result = await run_ensemble(
            prompt="Test",
            llm=llm,
            ensemble_size=1,
            runs_dir="/tmp/pythia_test_ensemble_single",
        )

        assert result.ensemble_size == 1
        assert len(result.runs) == 1
        assert result.agreement_ratio == 1.0


class TestNamedConstants:
    def test_default_ensemble_size(self):
        assert DEFAULT_ENSEMBLE_SIZE == 3

    def test_robust_threshold(self):
        assert ROBUST_HERD_MOMENT_THRESHOLD == 2

    def test_agreement_threshold(self):
        assert 0.0 < ENSEMBLE_AGREEMENT_THRESHOLD < 1.0
