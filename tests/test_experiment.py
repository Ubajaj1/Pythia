"""Tests for the experiment runner wiring (pipeline stages are patched)."""

from types import SimpleNamespace

import pythia.experiment as exp
from pythia.models import AgentEvaluation


async def test_run_experiment_once_wires_clients_and_metrics(monkeypatch):
    seen = {}

    async def fake_analyze(prompt, llm, context=None, agent_count=None, tick_count=None):
        seen["analyze"] = (llm, agent_count, tick_count)
        return SimpleNamespace(tick_count=tick_count)

    async def fake_generate(blueprint, llm):
        seen["generate"] = llm
        return [SimpleNamespace(id="a")]

    class FakeEngine:
        def __init__(self, blueprint, agents, llm, grounding_context=None):
            seen["engine"] = llm

        async def run(self):
            return ["tick"]

    fake_result = SimpleNamespace(summary=SimpleNamespace(final_aggregate_stance=0.3))

    monkeypatch.setattr(exp, "analyze_scenario", fake_analyze)
    monkeypatch.setattr(exp, "generate_agents", fake_generate)
    monkeypatch.setattr(exp, "SimulationEngine", FakeEngine)
    monkeypatch.setattr(exp, "build_run_result", lambda p, b, a, t: fake_result)

    async def fake_eval(result, agents, llm):
        seen["judge"] = llm
        return [AgentEvaluation(agent_id="a", is_coherent=True), AgentEvaluation(agent_id="b", is_coherent=False)]

    monkeypatch.setattr(exp, "evaluate_run", fake_eval)
    monkeypatch.setattr(exp, "run_metrics", lambda r: {"direction": "sell"})

    main, tick, judge = object(), object(), object()
    run = await exp.run_experiment_once("q", main, tick, judge, agent_count=5, tick_count=8)

    assert seen["analyze"] == (main, 5, 8)
    assert seen["generate"] is main
    assert seen["engine"] is tick
    assert seen["judge"] is judge
    assert run.metrics == {"direction": "sell"}
    assert run.coherence_rate == 0.5


def test_readme_prompts_has_five():
    assert len(exp.README_PROMPTS) == 5
