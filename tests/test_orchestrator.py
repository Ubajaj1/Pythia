"""Tests for the simulation orchestrator."""

import json
import os
import pytest
from tests.conftest import FakeLLMClient
from pythia.orchestrator import run_simulation
from pythia.models import RunResult, RunResultWithInsights


# Canned LLM responses: 1 analyzer + 2 generator pass1 + 1 generator pass2 + (3 ticks × 2 agents)
ANALYZER_RESPONSE = {
    "scenario_type": "market_event",
    "title": "Test Event",
    "description": "A test simulation",
    "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
    "agent_archetypes": [
        {"role": "trader", "count": 1, "description": "d", "bias": "loss_aversion", "stance_range": [0.2, 0.4]},
        {"role": "analyst", "count": 1, "description": "d", "bias": "anchoring", "stance_range": [0.6, 0.8]},
    ],
    "dynamics": "Test",
    "tick_count": 3,
}

GEN_PASS1_TRADER = {
    "agents": [{
        "id": "trader-t", "name": "Trader T", "role": "trader",
        "persona": "A trader.", "bias": "loss_aversion",
        "initial_stance": 0.2, "behavioral_rules": ["Sells on dips"],
    }]
}

GEN_PASS1_ANALYST = {
    "agents": [{
        "id": "analyst-a", "name": "Analyst A", "role": "analyst",
        "persona": "An analyst.", "bias": "anchoring",
        "initial_stance": 0.8, "behavioral_rules": ["Holds steady"],
    }]
}

GEN_PASS2 = {
    "relationships": {
        "trader-t": [{"target": "analyst-a", "type": "follows", "weight": 0.5}],
        "analyst-a": [{"target": "trader-t", "type": "respects", "weight": 0.3}],
    }
}

TICK_TRADER = {
    "stance": 0.28, "action": "sell", "emotion": "anxious",
    "reasoning": "Bad vibes", "message": "Selling.", "influence_target": "analyst-a",
}

TICK_ANALYST = {
    "stance": 0.72, "action": "hold", "emotion": "steady",
    "reasoning": "Fundamentals ok", "message": "Holding.", "influence_target": "trader-t",
}


def make_all_responses() -> list[dict]:
    """1 analyzer + 2 gen pass1 + 1 gen pass2 + 3 ticks × 2 agents = 10 calls."""
    return [
        ANALYZER_RESPONSE,
        GEN_PASS1_TRADER, GEN_PASS1_ANALYST,
        GEN_PASS2,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
    ]


class TestRunSimulation:
    async def test_produces_valid_run_result(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert isinstance(result, RunResultWithInsights)
        assert result.scenario.title == "Test Event"
        assert len(result.agents) == 2
        assert len(result.ticks) == 3

    async def test_saves_run_json_to_disk(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        run_file = tmp_path / f"{result.run_id}.json"
        assert run_file.exists()
        data = json.loads(run_file.read_text())
        assert data["run_id"] == result.run_id

    async def test_summary_has_correct_tick_count(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert result.summary.total_ticks == 3

    async def test_biggest_shift_identified(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert result.summary.biggest_shift.agent_id in ("trader-t", "analyst-a")

    async def test_context_passed_through(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        await run_simulation(
            prompt="Test event",
            context="Extra context here",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        # First call is the analyzer — context should appear in prompt
        assert "Extra context here" in llm.calls[0]["prompt"]
