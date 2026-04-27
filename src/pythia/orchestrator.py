"""Orchestrator — wires Analyzer → Generator → Engine → RunResult with insights."""

from __future__ import annotations

import logging
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
    GroundingContext,
    RunResultWithInsights,
    ScenarioInfo,
)
from pythia.summary import build_run_result, generate_run_id

logger = logging.getLogger(__name__)


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

    result = build_run_result(prompt, blueprint, agents, tick_records)

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
    (runs_path / f"{result.run_id}.json").write_text(
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

    # 5. Build result (shared logic with oracle loop)
    result = build_run_result(prompt, blueprint, agents, ticks)

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
    output_file = runs_path / f"{result.run_id}.json"
    output_file.write_text(enriched.model_dump_json(indent=2, by_alias=True))

    return enriched
