"""Oracle Loop — orchestrates multi-run simulate → evaluate → amend cycle."""

from __future__ import annotations

import logging
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
