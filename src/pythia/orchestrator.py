"""Orchestrator — wires Analyzer → Generator → Engine → RunResult with insights."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pythia.analyzer import analyze_scenario
from pythia.config import RUNS_DIR
from pythia.decision import generate_decision_summary
from pythia.engine import SimulationEngine
from pythia.generator import generate_agents
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.llm import LLMClient
from pythia.models import (
    AgentInfo,
    BiggestShift,
    GroundingContext,
    RunResult,
    RunResultWithInsights,
    RunSummary,
    ScenarioInfo,
)

logger = logging.getLogger(__name__)


def _generate_run_id() -> str:
    now = datetime.now(timezone.utc)
    return f"run_{now.strftime('%Y-%m-%d_%H%M%S')}"


def _compute_summary(result_partial: dict) -> RunSummary:
    """Compute run summary from ticks and agents."""
    ticks = result_partial["ticks"]
    agents = result_partial["agents"]

    total_ticks = len(ticks)
    final_aggregate = ticks[-1].aggregate_stance if ticks else 0.0

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


async def _maybe_ground(
    prompt: str,
    document_text: str | None,
    document_name: str | None,
    llm: LLMClient,
) -> GroundingContext | None:
    """Extract grounding from document if provided. Returns None if no document."""
    if not document_text:
        return None
    return await extract_grounding(
        document_text=document_text,
        prompt=prompt,
        llm=llm,
        source_name=document_name or "uploaded document",
    )


async def stream_simulation(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    fast_llm: LLMClient | None = None,
    document_text: str | None = None,
    document_name: str | None = None,
):
    """Async generator streaming SSE-ready dicts.

    Flow: thinking → grounding? → blueprint → scenario → tick×N → decision → done.
    """
    yield {"type": "thinking"}

    # Optional grounding from documents
    grounding = await _maybe_ground(prompt, document_text, document_name, llm)
    grounding_text = format_grounding_for_prompt(grounding)

    # Merge grounding into context for the analyzer
    enriched_context = context or ""
    if grounding_text:
        enriched_context = (enriched_context + "\n" + grounding_text).strip()
        yield {"type": "grounding", "data": grounding.model_dump(mode="json")}

    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
    )
    yield {
        "type": "blueprint",
        "data": {
            "title": blueprint.title,
            "tick_count": blueprint.tick_count,
            "stance_spectrum": blueprint.stance_spectrum,
        },
    }

    agents = await generate_agents(blueprint, llm=llm)
    agent_infos = [
        AgentInfo(id=a.id, name=a.name, role=a.role, persona=a.persona,
                  bias=a.bias, initial_stance=a.initial_stance)
        for a in agents
    ]
    yield {
        "type": "scenario",
        "data": {
            "title": blueprint.title,
            "scenario_type": blueprint.scenario_type,
            "stance_spectrum": blueprint.stance_spectrum,
            "tick_count": blueprint.tick_count,
            "agents": [ai.model_dump(mode="json") for ai in agent_infos],
        },
    }

    engine = SimulationEngine(
        blueprint=blueprint, agents=agents, llm=fast_llm or llm,
        grounding_context=grounding_text,
    )
    tick_records: list = []
    async for tick_record in engine.run_stream():
        tick_records.append(tick_record)
        yield {"type": "tick", "data": tick_record.model_dump(mode="json")}

    run_id = _generate_run_id()
    partial = {"ticks": tick_records, "agents": agents}
    summary = _compute_summary(partial)
    result = RunResult(
        run_id=run_id,
        scenario=ScenarioInfo(input=prompt, type=blueprint.scenario_type,
                              title=blueprint.title, stance_spectrum=blueprint.stance_spectrum),
        agents=agent_infos,
        ticks=tick_records,
        summary=summary,
    )

    # Generate decision summary from influence graph
    decision_summary = await generate_decision_summary(result, engine.influence_graph, llm)

    enriched = RunResultWithInsights(
        run_id=result.run_id,
        scenario=result.scenario,
        agents=result.agents,
        ticks=result.ticks,
        summary=result.summary,
        influence_graph=engine.influence_graph,
        decision_summary=decision_summary,
    )

    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    (runs_path / f"{run_id}.json").write_text(
        enriched.model_dump_json(indent=2, by_alias=True)
    )

    yield {"type": "done", "data": enriched.model_dump(mode="json")}


async def run_simulation(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    document_text: str | None = None,
    document_name: str | None = None,
) -> RunResultWithInsights:
    """Run the full simulation pipeline and return enriched results."""
    # 1. Optional grounding
    grounding = await _maybe_ground(prompt, document_text, document_name, llm)
    grounding_text = format_grounding_for_prompt(grounding)

    enriched_context = context or ""
    if grounding_text:
        enriched_context = (enriched_context + "\n" + grounding_text).strip()

    # 2. Analyze scenario
    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
    )

    # 3. Generate agents
    agents = await generate_agents(blueprint, llm=llm)

    # 4. Run simulation with influence tracking
    engine = SimulationEngine(
        blueprint=blueprint, agents=agents, llm=llm,
        grounding_context=grounding_text,
    )
    ticks = await engine.run()

    # 5. Build result
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
            input=prompt, type=blueprint.scenario_type,
            title=blueprint.title, stance_spectrum=blueprint.stance_spectrum,
        ),
        agents=agent_infos,
        ticks=ticks,
        summary=summary,
    )

    # 6. Generate decision summary
    decision_summary = await generate_decision_summary(
        result, engine.influence_graph, llm,
    )

    enriched = RunResultWithInsights(
        run_id=result.run_id,
        scenario=result.scenario,
        agents=result.agents,
        ticks=result.ticks,
        summary=result.summary,
        influence_graph=engine.influence_graph,
        decision_summary=decision_summary,
    )

    # 7. Save to disk
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    output_file = runs_path / f"{run_id}.json"
    output_file.write_text(enriched.model_dump_json(indent=2, by_alias=True))

    return enriched
