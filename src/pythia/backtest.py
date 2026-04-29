"""Backtest runner — runs Pythia against known outcomes to measure accuracy.

In past_event mode:
1. Agents are blinded to the outcome — they simulate as if forecasting.
2. After the simulation, the predicted aggregate is compared to the actual outcome.
3. CalibrationScore measures direction correctness, aggregate error, and confidence match.

The batch runner processes all cases in data/ground_truth/ and produces a CalibrationReport.
"""

from __future__ import annotations

import logging

from pythia.analyzer import analyze_scenario, resolve_preset
from pythia.calibration import (
    compute_calibration_report,
    compute_calibration_score,
    load_ground_truth_cases,
)
from pythia.config import RUNS_DIR
from pythia.decision import generate_decision_summary
from pythia.engine import SimulationEngine
from pythia.generator import generate_agents
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.llm import LLMClient
from pythia.models import (
    BacktestCase,
    BacktestResult,
    CalibrationReport,
    GroundTruthOutcome,
    RunResultWithInsights,
)
from pythia.summary import build_run_result, generate_run_id

logger = logging.getLogger(__name__)


async def run_backtest(
    prompt: str,
    ground_truth: GroundTruthOutcome,
    llm: LLMClient,
    context: str | None = None,
    document_text: str | None = None,
    document_name: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> tuple[RunResultWithInsights, BacktestResult]:
    """Run a single backtest: simulate blinded, then score against ground truth.

    Returns both the full enriched run result and the calibration score.
    """
    logger.info("Backtest started prompt=%r", prompt[:60])

    # Resolve preset
    preset_vals = resolve_preset(preset)
    final_agents = agent_count or preset_vals.get("agent_count")
    final_ticks = tick_count or preset_vals.get("tick_count")

    # Optional grounding (blinded — no outcome info in the document)
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

    # Analyze + generate + run (agents are blinded — no ground truth in prompts)
    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
        agent_count=final_agents, tick_count=final_ticks,
    )
    agents = await generate_agents(blueprint, llm=llm)

    engine = SimulationEngine(
        blueprint=blueprint, agents=agents, llm=llm,
        grounding_context=grounding_text,
    )
    ticks = await engine.run()

    run_id = generate_run_id(prefix="backtest")
    result = build_run_result(prompt, blueprint, agents, ticks, run_id=run_id)

    decision_summary = await generate_decision_summary(
        result, engine.influence_graph, llm, has_grounding=bool(grounding),
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

    # Score against ground truth
    predicted_confidence = decision_summary.confidence if decision_summary else "low"
    calibration = compute_calibration_score(
        predicted_aggregate=result.summary.final_aggregate_stance,
        predicted_confidence=predicted_confidence,
        actual=ground_truth,
    )

    backtest_result = BacktestResult(
        case_id=run_id,
        prompt=prompt,
        predicted_aggregate=result.summary.final_aggregate_stance,
        predicted_confidence=predicted_confidence,
        actual_aggregate=ground_truth.aggregate_stance,
        actual_confidence=ground_truth.confidence,
        calibration=calibration,
        run_id=run_id,
    )

    logger.info(
        "Backtest complete direction=%s error=%.3f confidence_match=%s",
        calibration.direction_correct, calibration.aggregate_error,
        calibration.confidence_match,
    )

    return enriched, backtest_result


async def run_batch_backtest(
    llm: LLMClient,
    ground_truth_dir: str = "data/ground_truth",
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> CalibrationReport:
    """Run all ground-truth cases and produce a calibration report.

    Cases are loaded from JSON files in ground_truth_dir.
    Runs sequentially to avoid overwhelming the LLM provider.
    """
    cases = load_ground_truth_cases(ground_truth_dir)
    if not cases:
        logger.warning("No ground truth cases found in %s", ground_truth_dir)
        return compute_calibration_report([])

    logger.info("Batch backtest started cases=%d", len(cases))

    results: list[BacktestResult] = []
    for i, case in enumerate(cases, 1):
        logger.info("Batch case %d/%d: %s", i, len(cases), case.case_id or case.prompt[:40])
        try:
            _, bt_result = await run_backtest(
                prompt=case.prompt,
                ground_truth=case.ground_truth_outcome,
                llm=llm,
                context=case.context,
                document_text=case.document_text,
                agent_count=agent_count,
                tick_count=tick_count,
                preset=preset,
                runs_dir=runs_dir,
            )
            bt_result = bt_result.model_copy(update={"case_id": case.case_id or f"case-{i}"})
            results.append(bt_result)
        except Exception as exc:
            logger.error("Batch case %d failed: %s", i, exc)

    report = compute_calibration_report(results)
    logger.info(
        "Batch backtest complete cases=%d direction_accuracy=%.0f%% mean_error=%.3f",
        report.total_cases, report.direction_accuracy * 100, report.mean_aggregate_error,
    )
    return report
