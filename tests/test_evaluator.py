"""Tests for the agent reasoning evaluator."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.evaluator import evaluate_agent, evaluate_run
from pythia.models import (
    Agent, AgentEvaluation, RunResult, ScenarioInfo, AgentInfo,
    TickEvent, TickRecord, RunSummary, BiggestShift,
)


def make_agent(agent_id="agent-a", rules=None):
    return Agent(
        id=agent_id, name="Agent A", role="trader",
        persona="Cautious trader.", bias="loss_aversion",
        initial_stance=0.3,
        behavioral_rules=rules or ["Sells on bad news"],
    )


def make_tick_pairs(agent_id="agent-a", n=3):
    return [
        (i + 1, TickEvent(
            agent_id=agent_id,
            stance=0.3 - i * 0.02,
            previous_stance=0.3 - (i - 1) * 0.02 if i > 0 else 0.3,
            action="sell", emotion="anxious",
            reasoning=f"Bad signals at tick {i + 1}",
            message="Selling.", influence_target=None,
        ))
        for i in range(n)
    ]


def make_run_result(agent_ids=("agent-a", "agent-b")):
    tick_records = [
        TickRecord(
            tick=1,
            events=[
                TickEvent(
                    agent_id=aid, stance=0.3, previous_stance=0.3,
                    action="hold", emotion="neutral", reasoning="ok",
                    message="ok", influence_target=None,
                )
                for aid in agent_ids
            ],
            aggregate_stance=0.5,
        )
    ]
    return RunResult(
        run_id="run_test",
        scenario=ScenarioInfo(
            input="test", type="market", title="Test",
            stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        ),
        agents=[
            AgentInfo(id=aid, name=f"Agent {aid}", role="trader",
                      persona="p", bias="b", initial_stance=0.5)
            for aid in agent_ids
        ],
        ticks=tick_records,
        summary=RunSummary(
            total_ticks=1, final_aggregate_stance=0.5,
            biggest_shift=BiggestShift(
                agent_id="agent-a", from_stance=0.3, to_stance=0.3, reason="",
            ),
            consensus_reached=True,
        ),
    )


class TestEvaluateAgent:
    async def test_coherent_agent_returns_is_coherent_true(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent()
        tick_pairs = make_tick_pairs()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.agent_id == "agent-a"
        assert result.is_coherent is True
        assert result.incoherence_summary is None

    async def test_incoherent_agent_returns_is_coherent_false(self):
        llm = FakeLLMClient(responses=[{
            "is_coherent": False,
            "incoherence_summary": "Agent claimed loss-aversion but bought with no explanation",
        }])
        agent = make_agent()
        tick_pairs = make_tick_pairs()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.is_coherent is False
        assert result.incoherence_summary is not None

    async def test_eval_prompt_contains_agent_behavioral_rules(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent(rules=["Never panic sell", "Always check fundamentals"])
        tick_pairs = make_tick_pairs()

        await evaluate_agent(agent, tick_pairs, llm)

        assert "Never panic sell" in llm.calls[0]["prompt"]
        assert "Always check fundamentals" in llm.calls[0]["prompt"]

    async def test_eval_prompt_contains_tick_history(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent()
        tick_pairs = make_tick_pairs()

        await evaluate_agent(agent, tick_pairs, llm)

        assert "Bad signals at tick 1" in llm.calls[0]["prompt"]

    async def test_missing_is_coherent_in_response_defaults_to_true(self):
        llm = FakeLLMClient(responses=[{}])
        agent = make_agent()
        tick_pairs = make_tick_pairs()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.is_coherent is True


class TestEvaluateRun:
    async def test_returns_one_evaluation_per_agent(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None},
            {"is_coherent": True, "incoherence_summary": None},
        ])
        agents = [make_agent("agent-a"), make_agent("agent-b")]
        run_result = make_run_result(("agent-a", "agent-b"))

        evals = await evaluate_run(run_result, agents, llm)

        assert len(evals) == 2
        assert {e.agent_id for e in evals} == {"agent-a", "agent-b"}

    async def test_returns_list_of_agent_evaluations(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": False, "incoherence_summary": "Contradiction"},
            {"is_coherent": True, "incoherence_summary": None},
        ])
        agents = [make_agent("agent-a"), make_agent("agent-b")]
        run_result = make_run_result(("agent-a", "agent-b"))

        evals = await evaluate_run(run_result, agents, llm)

        assert all(isinstance(e, AgentEvaluation) for e in evals)
        failing = [e for e in evals if not e.is_coherent]
        assert len(failing) == 1
