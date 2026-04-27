"""Oracle Loop — orchestrates multi-run simulate → evaluate → amend cycle."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pythia.analyzer import analyze_scenario
from pythia.config import RUNS_DIR
from pythia.decision import generate_decision_summary
from pythia.engine import SimulationEngine
from pythia.evaluator import evaluate_run, extract_agent_tick_pairs
from pythia.generator import generate_agents
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.llm import LLMClient
from pythia.models import (
    Agent,
    AgentInfo,
    BiggestShift,
    InfluenceGraph,
    OracleLoopResult,
    OracleRunRecord,
    RunResult,
    RunSummary,
    ScenarioBlueprint,
    ScenarioInfo,
    TickRecord,
)
from pythia.temple import amend_agent

logger = logging.getLogger(__name__)


def _build_run_result(
    run_num: int,
    prompt: str,
    blueprint: ScenarioBlueprint,
    agents: list[Agent],
    ticks: list[TickRecord],
    runs_dir: str,
) -> RunResult:
    """Build and save a RunResult for one oracle run."""
    now = datetime.now(timezone.utc)
    run_id = f"oracle_{now.strftime('%Y-%m-%d_%H%M%S')}_r{run_num}"

    agent_infos = [
        AgentInfo(
            id=a.id, name=a.name, role=a.role,
            persona=a.persona, bias=a.bias,
            initial_stance=a.initial_stance,
        )
        for a in agents
    ]

    total_ticks = len(ticks)
    final_aggregate = ticks[-1].aggregate_stance if ticks else 0.0

    agent_initial = {a.id: a.initial_stance for a in agents}
    agent_final: dict[str, float] = {}
    agent_last_reasoning: dict[str, str] = {}
    for tick in ticks:
        for event in tick.events:
            agent_final[event.agent_id] = event.stance
            agent_last_reasoning[event.agent_id] = event.reasoning

    biggest_id = max(
        agent_final,
        key=lambda aid: abs(agent_final[aid] - agent_initial.get(aid, 0.5)),
        default="",
    )
    final_stances = list(agent_final.values())
    consensus = (max(final_stances) - min(final_stances)) < 0.15 if final_stances else False

    summary = RunSummary(
        total_ticks=total_ticks,
        final_aggregate_stance=round(final_aggregate, 4),
        biggest_shift=BiggestShift(
            agent_id=biggest_id,
            from_stance=round(agent_initial.get(biggest_id, 0.5), 4),
            to_stance=round(agent_final.get(biggest_id, 0.5), 4),
            reason=agent_last_reasoning.get(biggest_id, ""),
        ),
        consensus_reached=consensus,
    )

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

    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    (runs_path / f"{run_id}.json").write_text(result.model_dump_json(indent=2, by_alias=True))
    logger.debug("Run result saved run_id=%s path=%s", run_id, runs_path / f"{run_id}.json")

    return result


async def run_oracle_loop(
    prompt: str,
    llm: LLMClient,
    max_runs: int = 5,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    document_text: str | None = None,
    document_name: str | None = None,
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

    # Optional document grounding
    grounding = None
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
        run_result = _build_run_result(run_num, prompt, blueprint, agents, ticks, runs_dir)

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
