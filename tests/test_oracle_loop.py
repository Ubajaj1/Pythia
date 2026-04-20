"""Tests for the Oracle Loop orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import FakeLLMClient
from pythia.oracle_loop import run_oracle_loop
from pythia.models import Agent, AgentEvaluation, OracleLoopResult


# --- Canned LLM responses (same format as test_orchestrator.py) ---

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


def make_sim_responses():
    """1 analyze + 2 gen_pass1 + 1 gen_pass2 + 3 ticks × 2 agents = 10 responses."""
    return [
        ANALYZER_RESPONSE,
        GEN_PASS1_TRADER, GEN_PASS1_ANALYST,
        GEN_PASS2,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
    ]


def make_run2_responses():
    """Run 2 skips analyze+generate, only needs 3 ticks × 2 agents = 6 responses."""
    return [TICK_TRADER, TICK_ANALYST] * 3


ALL_COHERENT = [
    AgentEvaluation(agent_id="trader-t", is_coherent=True, incoherence_summary=None),
    AgentEvaluation(agent_id="analyst-a", is_coherent=True, incoherence_summary=None),
]

ONE_FAILING = [
    AgentEvaluation(agent_id="trader-t", is_coherent=False, incoherence_summary="Contradiction"),
    AgentEvaluation(agent_id="analyst-a", is_coherent=True, incoherence_summary=None),
]

AMENDED_TRADER = Agent(
    id="trader-t", name="Trader T", role="trader",
    persona="A trader.", bias="loss_aversion",
    initial_stance=0.2,
    behavioral_rules=["Sells on dips", "State reason when overriding default behavior"],
)


class TestRunOracleLoop:
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_stops_after_one_run_when_all_coherent(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert isinstance(result, OracleLoopResult)
        assert len(result.runs) == 1
        assert mock_eval.call_count == 1

    @patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock)
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_runs_twice_when_one_agent_fails_then_all_pass(
        self, mock_eval, mock_amend, tmp_path
    ):
        mock_eval.side_effect = [ONE_FAILING, ALL_COHERENT]
        mock_amend.return_value = AMENDED_TRADER
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert len(result.runs) == 2
        assert mock_amend.call_count == 1  # only trader-t failed

    @patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock)
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_records_amended_agent_ids(self, mock_eval, mock_amend, tmp_path):
        mock_eval.side_effect = [ONE_FAILING, ALL_COHERENT]
        mock_amend.return_value = AMENDED_TRADER
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert result.runs[0].amended_agent_ids == ["trader-t"]
        assert result.runs[1].amended_agent_ids == []

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_coherence_history_length_equals_run_count(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=3, runs_dir=str(tmp_path))

        assert len(result.coherence_history) == len(result.runs)

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_coherence_score_is_fraction_of_coherent_agents(self, mock_eval, tmp_path):
        mock_eval.return_value = ONE_FAILING  # 1 of 2 failing = 0.5 coherent
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=1, runs_dir=str(tmp_path))

        assert result.runs[0].coherence_score == 0.5

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_respects_max_runs_limit(self, mock_eval, tmp_path):
        mock_eval.return_value = ONE_FAILING
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        with patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock) as mock_amend:
            mock_amend.return_value = AMENDED_TRADER
            result = await run_oracle_loop("Test event", llm, max_runs=2, runs_dir=str(tmp_path))

        assert len(result.runs) == 2

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_saves_each_run_json_to_disk(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=1, runs_dir=str(tmp_path))

        run_id = result.runs[0].result.run_id
        assert (tmp_path / f"{run_id}.json").exists()

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_prompt_preserved_in_result(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("My unique prompt", llm, max_runs=1, runs_dir=str(tmp_path))

        assert result.prompt == "My unique prompt"
