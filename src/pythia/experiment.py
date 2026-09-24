"""Single-run experiment pipeline with separate main / tick / judge clients."""

from __future__ import annotations

from dataclasses import dataclass

from pythia.analyzer import analyze_scenario
from pythia.engine import SimulationEngine
from pythia.eval_metrics import run_metrics
from pythia.evaluator import evaluate_run
from pythia.generator import generate_agents
from pythia.llm import LLMClient
from pythia.models import AgentEvaluation, RunResult
from pythia.summary import build_run_result

README_PROMPTS = [
    "Should our startup adopt AI coding tools for all engineering tasks?",
    "Should we raise a Series A or stay bootstrapped?",
    "Should a city ban single-use plastics in restaurants?",
    "Should tech companies mandate a return to office 5 days a week?",
    "Should a social media platform ban political advertising entirely?",
]


@dataclass
class ExperimentRun:
    prompt: str
    result: RunResult
    evaluations: list[AgentEvaluation]
    metrics: dict[str, float | str]

    @property
    def coherence_rate(self) -> float:
        if not self.evaluations:
            return 0.0
        return sum(1 for e in self.evaluations if e.is_coherent) / len(self.evaluations)


async def run_experiment_once(
    prompt: str,
    main_llm: LLMClient,
    tick_llm: LLMClient,
    judge_llm: LLMClient,
    agent_count: int = 5,
    tick_count: int = 8,
) -> ExperimentRun:
    blueprint = await analyze_scenario(
        prompt, llm=main_llm, agent_count=agent_count, tick_count=tick_count,
    )
    agents = await generate_agents(blueprint, llm=main_llm)
    engine = SimulationEngine(blueprint=blueprint, agents=agents, llm=tick_llm)
    ticks = await engine.run()
    result = build_run_result(prompt, blueprint, agents, ticks)
    evaluations = await evaluate_run(result, agents, judge_llm)
    return ExperimentRun(prompt=prompt, result=result, evaluations=evaluations, metrics=run_metrics(result))
