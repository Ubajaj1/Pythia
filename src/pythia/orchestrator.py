"""Orchestrator — wires Analyzer → Generator → Engine → RunResult."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pythia.analyzer import analyze_scenario
from pythia.config import RUNS_DIR
from pythia.engine import SimulationEngine
from pythia.generator import generate_agents
from pythia.llm import LLMClient
from pythia.models import (
    AgentInfo,
    BiggestShift,
    RunResult,
    RunSummary,
    ScenarioInfo,
)


def _generate_run_id() -> str:
    now = datetime.now(timezone.utc)
    return f"run_{now.strftime('%Y-%m-%d_%H%M%S')}"


def _compute_summary(result_partial: dict) -> RunSummary:
    """Compute run summary from ticks and agents."""
    ticks = result_partial["ticks"]
    agents = result_partial["agents"]

    total_ticks = len(ticks)
    final_aggregate = ticks[-1].aggregate_stance if ticks else 0.0

    # Find biggest shift: compare each agent's final stance to initial
    agent_initial = {a.id: a.initial_stance for a in agents}
    agent_final: dict[str, float] = {}
    agent_last_reasoning: dict[str, str] = {}
    for tick in ticks:
        for event in tick.events:
            agent_final[event.agent_id] = event.stance
            agent_last_reasoning[event.agent_id] = event.reasoning

    biggest_id = ""
    biggest_delta = 0.0
    for aid, final in agent_final.items():
        initial = agent_initial.get(aid, 0.5)
        delta = abs(final - initial)
        if delta > biggest_delta:
            biggest_delta = delta
            biggest_id = aid

    initial_val = agent_initial.get(biggest_id, 0.5)
    final_val = agent_final.get(biggest_id, 0.5)

    # Consensus: all agents within 0.15 of each other
    final_stances = list(agent_final.values())
    consensus = (max(final_stances) - min(final_stances)) < 0.15 if final_stances else False

    return RunSummary(
        total_ticks=total_ticks,
        final_aggregate_stance=round(final_aggregate, 4),
        biggest_shift=BiggestShift(
            agent_id=biggest_id,
            from_stance=round(initial_val, 4),
            to_stance=round(final_val, 4),
            reason=agent_last_reasoning.get(biggest_id, ""),
        ),
        consensus_reached=consensus,
    )


async def run_simulation(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> RunResult:
    """Run the full simulation pipeline and return a RunResult."""
    # 1. Analyze scenario
    blueprint = await analyze_scenario(prompt, llm=llm, context=context)

    # 2. Generate agents
    agents = await generate_agents(blueprint, llm=llm)

    # 3. Run simulation
    engine = SimulationEngine(blueprint=blueprint, agents=agents, llm=llm)
    ticks = await engine.run()

    # 4. Build result
    run_id = _generate_run_id()

    agent_infos = [
        AgentInfo(
            id=a.id, name=a.name, role=a.role,
            persona=a.persona, bias=a.bias,
            initial_stance=a.initial_stance,
        )
        for a in agents
    ]

    partial = {"ticks": ticks, "agents": agents}
    summary = _compute_summary(partial)

    result = RunResult(
        run_id=run_id,
        scenario=ScenarioInfo(
            input=prompt,
            type=blueprint.scenario_type,
            title=blueprint.title,
            stance_spectrum=blueprint.stance_spectrum,
        ),
        agents=agent_infos,
        ticks=ticks,
        summary=summary,
    )

    # 5. Save to disk
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    output_file = runs_path / f"{run_id}.json"
    output_file.write_text(result.model_dump_json(indent=2, by_alias=True))

    return result
