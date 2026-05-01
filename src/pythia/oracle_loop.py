"""Oracle Loop — orchestrates multi-run simulate → evaluate → amend cycle."""

from __future__ import annotations

import logging
from pathlib import Path

from pythia.analyzer import analyze_scenario, resolve_preset
from pythia.config import RUNS_DIR
from pythia.decision import generate_decision_summary
from pythia.engine import SimulationEngine
from pythia.evaluator import evaluate_run, extract_agent_tick_pairs
from pythia.generator import generate_agents
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.llm import LLMClient
from pythia.models import (
    Agent,
    InfluenceGraph,
    OracleLoopResult,
    OracleRunRecord,
)
from pythia.summary import build_run_result, generate_run_id
from pythia.temple import amend_agent

logger = logging.getLogger(__name__)


async def run_oracle_loop(
    prompt: str,
    llm: LLMClient,
    max_runs: int = 5,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    document_text: str | None = None,
    document_name: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
) -> OracleLoopResult:
    """Run up to max_runs iterations of simulate → evaluate → amend.

    Stops early if all agents pass coherence evaluation.
    Re-uses blueprint and (amended) agents across runs — no re-analysis.
    Optionally grounds the simulation with document data.
    """
    logger.info(
        "Oracle Loop started prompt=%r max_runs=%d",
        prompt[:60] + ("..." if len(prompt) > 60 else ""), max_runs,
    )

    # Resolve preset + explicit overrides
    preset_vals = resolve_preset(preset)
    final_agents = agent_count or preset_vals.get("agent_count")
    final_ticks = tick_count or preset_vals.get("tick_count")

    # Optional document grounding
    grounding_text = ""
    if document_text:
        grounding = await extract_grounding(
            document_text=document_text, prompt=prompt, llm=llm,
            source_name=document_name or "uploaded document",
        )
        grounding_text = format_grounding_for_prompt(grounding)

    enriched_context = context or ""
    if grounding_text:
        enriched_context = (enriched_context + "\n" + grounding_text).strip()

    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
        agent_count=final_agents, tick_count=final_ticks,
    )
    agents = await generate_agents(blueprint, llm=llm)

    run_records: list[OracleRunRecord] = []
    last_influence_graph: InfluenceGraph | None = None

    for run_num in range(1, max_runs + 1):
        logger.info("Oracle run %d/%d started agents=%d", run_num, max_runs, len(agents))

        engine = SimulationEngine(
            blueprint=blueprint, agents=agents, llm=llm,
            grounding_context=grounding_text,
        )
        ticks = await engine.run()
        last_influence_graph = engine.influence_graph

        # Build result using shared logic (same summary computation as orchestrator)
        run_id = generate_run_id(prefix="oracle")
        run_result = build_run_result(prompt, blueprint, agents, ticks, run_id=run_id)

        # Save to disk
        runs_path = Path(runs_dir)
        runs_path.mkdir(parents=True, exist_ok=True)
        (runs_path / f"{run_id}.json").write_text(
            run_result.model_dump_json(indent=2, by_alias=True)
        )

        evaluations = await evaluate_run(run_result, agents, llm)
        coherence_score = sum(1 for e in evaluations if e.is_coherent) / len(evaluations)
        failing = [e for e in evaluations if not e.is_coherent]

        logger.info(
            "Oracle run %d/%d complete coherence=%.1f%% (%d/%d coherent) failing=%s",
            run_num, max_runs, coherence_score * 100,
            len(evaluations) - len(failing), len(evaluations),
            [e.agent_id for e in failing] or "none",
        )

        run_records.append(OracleRunRecord(
            run_number=run_num,
            result=run_result,
            evaluations=evaluations,
            coherence_score=round(coherence_score, 4),
            amended_agent_ids=[e.agent_id for e in failing],
        ))

        if not failing:
            logger.info("All agents coherent — stopping early after %d run(s)", run_num)
            break

        if run_num < max_runs:
            logger.info("Amending %d failing agent(s) before run %d", len(failing), run_num + 1)
            amended_agents = []
            for agent in agents:
                failing_eval = next((e for e in failing if e.agent_id == agent.id), None)
                if failing_eval:
                    tick_pairs = extract_agent_tick_pairs(run_result, agent.id)
                    amended = await amend_agent(agent, failing_eval, tick_pairs, llm)
                    amended_agents.append(amended)
                else:
                    amended_agents.append(agent)
            agents = amended_agents

    # Generate decision summary from the final run's data and influence graph
    decision_summary = None
    if run_records and last_influence_graph:
        final_result = run_records[-1].result
        decision_summary = await generate_decision_summary(
            final_result, last_influence_graph, llm,
            has_grounding=bool(document_text),
        )

    final_coherence = run_records[-1].coherence_score if run_records else 0.0
    logger.info(
        "Oracle Loop complete runs=%d final_coherence=%.1f%%",
        len(run_records), final_coherence * 100,
    )

    return OracleLoopResult(
        prompt=prompt,
        runs=run_records,
        coherence_history=[r.coherence_score for r in run_records],
        decision_summary=decision_summary,
        influence_graph=last_influence_graph,
    )


async def stream_oracle_loop(
    prompt: str,
    llm: LLMClient,
    max_runs: int = 5,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    fast_llm: LLMClient | None = None,
    document_text: str | None = None,
    document_name: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
):
    """Async generator streaming SSE-ready dicts for an Oracle loop.

    The Oracle loop is a multi-run analyze → simulate → evaluate → amend cycle.
    Without streaming, the UI has nothing to animate during what can be a
    several-minute process. This mirrors the single-simulate / ensemble
    stream protocol so the existing Arena/Stage handlers work unchanged.

    Events:
      - thinking
      - grounding (optional)
      - blueprint
      - scenario (agents shared across runs — same as ensemble)
      - run_start (per iteration, carries amended_agent_ids from previous run)
      - tick (per tick of the active run)
      - run_complete (per iteration, carries coherence_score + failing agents)
      - done (final OracleLoopResult)
    """
    logger.info(
        "Oracle stream started prompt=%r max_runs=%d",
        prompt[:60] + ("..." if len(prompt) > 60 else ""), max_runs,
    )

    # Resolve preset + explicit overrides
    preset_vals = resolve_preset(preset)
    final_agents = agent_count or preset_vals.get("agent_count")
    final_ticks = tick_count or preset_vals.get("tick_count")

    yield {"type": "thinking"}

    # Optional document grounding (once, shared across runs)
    grounding = None
    grounding_text = ""
    if document_text:
        grounding = await extract_grounding(
            document_text=document_text, prompt=prompt, llm=llm,
            source_name=document_name or "uploaded document",
        )
        grounding_text = format_grounding_for_prompt(grounding)
        yield {"type": "grounding", "data": grounding.model_dump(mode="json")}

    enriched_context = context or ""
    if grounding_text:
        enriched_context = (enriched_context + "\n" + grounding_text).strip()

    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
        agent_count=final_agents, tick_count=final_ticks,
    )
    yield {
        "type": "blueprint",
        "data": {
            "title": blueprint.title,
            "tick_count": blueprint.tick_count,
            "stance_spectrum": blueprint.stance_spectrum,
            "max_runs": max_runs,
        },
    }

    agents = await generate_agents(blueprint, llm=llm)

    # Emit the scenario once — the cast is stable across iterations, even
    # though individual agents may get amended (rules/bias_strength) between
    # runs. Those amendments don't change agent id/name/initial_stance so the
    # UI's Stage/protagonists stay valid.
    from pythia.models import AgentInfo  # noqa: PLC0415

    agent_infos = [
        AgentInfo(
            id=a.id, name=a.name, role=a.role, persona=a.persona,
            bias=a.bias, bias_strength=a.bias_strength,
            initial_stance=a.initial_stance,
        )
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
            "max_runs": max_runs,
        },
    }

    run_records: list[OracleRunRecord] = []
    last_influence_graph: InfluenceGraph | None = None
    previous_amended: list[str] = []

    for run_num in range(1, max_runs + 1):
        logger.info("Oracle stream run %d/%d started agents=%d", run_num, max_runs, len(agents))
        yield {
            "type": "run_start",
            "data": {
                "run_number": run_num,
                "max_runs": max_runs,
                # Agents amended by the previous iteration — lets the UI mark
                # them in the Stage before the new run animates.
                "amended_agent_ids": previous_amended,
            },
        }

        engine = SimulationEngine(
            blueprint=blueprint, agents=agents, llm=fast_llm or llm,
            grounding_context=grounding_text,
        )

        tick_records: list = []
        async for tick_record in engine.run_stream():
            tick_records.append(tick_record)
            yield {
                "type": "tick",
                "data": {
                    "run_number": run_num,
                    **tick_record.model_dump(mode="json"),
                },
            }

        last_influence_graph = engine.influence_graph

        run_id = generate_run_id(prefix="oracle")
        run_result = build_run_result(prompt, blueprint, agents, tick_records, run_id=run_id)

        runs_path = Path(runs_dir)
        runs_path.mkdir(parents=True, exist_ok=True)
        (runs_path / f"{run_id}.json").write_text(
            run_result.model_dump_json(indent=2, by_alias=True)
        )

        evaluations = await evaluate_run(run_result, agents, llm)
        coherence_score = sum(1 for e in evaluations if e.is_coherent) / len(evaluations)
        failing = [e for e in evaluations if not e.is_coherent]

        logger.info(
            "Oracle stream run %d/%d complete coherence=%.1f%% (%d/%d coherent) failing=%s",
            run_num, max_runs, coherence_score * 100,
            len(evaluations) - len(failing), len(evaluations),
            [e.agent_id for e in failing] or "none",
        )

        run_records.append(OracleRunRecord(
            run_number=run_num,
            result=run_result,
            evaluations=evaluations,
            coherence_score=round(coherence_score, 4),
            amended_agent_ids=[e.agent_id for e in failing],
        ))

        yield {
            "type": "run_complete",
            "data": {
                "run_number": run_num,
                "coherence_score": round(coherence_score, 4),
                "amended_agent_ids": [e.agent_id for e in failing],
                "will_amend": bool(failing) and run_num < max_runs,
            },
        }

        if not failing:
            logger.info(
                "Oracle stream: all agents coherent — stopping early after %d run(s)",
                run_num,
            )
            break

        if run_num < max_runs:
            logger.info(
                "Oracle stream: amending %d failing agent(s) before run %d",
                len(failing), run_num + 1,
            )
            amended_agents = []
            for agent in agents:
                failing_eval = next((e for e in failing if e.agent_id == agent.id), None)
                if failing_eval:
                    tick_pairs = extract_agent_tick_pairs(run_result, agent.id)
                    amended = await amend_agent(agent, failing_eval, tick_pairs, llm)
                    amended_agents.append(amended)
                else:
                    amended_agents.append(agent)
            agents = amended_agents
            previous_amended = [e.agent_id for e in failing]

    decision_summary = None
    if run_records and last_influence_graph:
        final_result = run_records[-1].result
        decision_summary = await generate_decision_summary(
            final_result, last_influence_graph, llm,
            has_grounding=bool(document_text),
        )

    final_coherence = run_records[-1].coherence_score if run_records else 0.0
    logger.info(
        "Oracle stream complete runs=%d final_coherence=%.1f%%",
        len(run_records), final_coherence * 100,
    )

    result = OracleLoopResult(
        prompt=prompt,
        runs=run_records,
        coherence_history=[r.coherence_score for r in run_records],
        decision_summary=decision_summary,
        influence_graph=last_influence_graph,
    )

    yield {"type": "done", "data": result.model_dump(mode="json")}
