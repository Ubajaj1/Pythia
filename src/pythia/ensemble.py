"""Ensemble runs — run the same scenario N times for statistical robustness.

One run is an anecdote. Three runs that agree are a signal. Three runs that
disagree tell you the scenario is genuinely uncertain and any single verdict
is misleading.

Agent generation happens once. Only the engine tick loop repeats per run.
Runs execute sequentially by default — parallel execution would overwhelm
local LLM providers like Ollama. Cloud APIs with high rate limits could
parallelize in the future.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from pythia.analyzer import analyze_scenario, resolve_preset
from pythia.config import RUNS_DIR
from pythia.decision import generate_decision_summary
from pythia.engine import SimulationEngine
from pythia.generator import generate_agents
from pythia.grounding import extract_grounding, format_grounding_for_prompt
from pythia.llm import LLMClient
from pythia.models import (
    EnsembleResult,
    InfluenceGraph,
    RunResultWithInsights,
)
from pythia.summary import build_run_result, generate_run_id

logger = logging.getLogger(__name__)

# ── Named constants ──────────────────────────────────────────────────────────

# Default number of runs. 3 is the minimum that detects instability:
# 2/3 agree = signal, all 3 disagree = genuine uncertainty.
DEFAULT_ENSEMBLE_SIZE = 3

# A herd moment must appear in at least this many runs to be called "robust."
# At N=3, this means 2+ runs. At N=5, still 2+ (conservative).
ROBUST_HERD_MOMENT_THRESHOLD = 2

# How closely runs must match on confidence label to be called "robust."
# At N=3, 2/3 agreement (0.6667) should count as consensus.
# Using 0.6 so that a simple majority at any ensemble size qualifies.
ENSEMBLE_AGREEMENT_THRESHOLD = 0.6


def _aggregate_ensemble(
    runs: list[RunResultWithInsights],
) -> dict:
    """Compute ensemble-level metrics from N completed runs.

    Returns a dict of fields to set on EnsembleResult.
    Pure function — no LLM calls, no side effects.
    """
    n = len(runs)
    if n == 0:
        return {
            "aggregate_distribution": [],
            "confidence_distribution": [],
            "agreement_ratio": 0.0,
            "ensemble_confidence": "low",
            "robust_herd_moments": [],
            "noisy_herd_moments": [],
        }

    # Collect per-run final aggregates and confidence labels
    aggregates = [r.summary.final_aggregate_stance for r in runs]
    confidences = [
        r.decision_summary.confidence if r.decision_summary else "low"
        for r in runs
    ]

    # Agreement: what fraction of runs share the most common confidence label
    conf_counts = Counter(confidences)
    most_common_label, most_common_count = conf_counts.most_common(1)[0]
    agreement_ratio = most_common_count / n

    # Ensemble confidence: if agreement is strong, use the consensus label.
    # Otherwise, use the worst-case (most cautious) label.
    _CONFIDENCE_RANK = {"low": 0, "polarized": 1, "moderate": 2, "high": 3}
    if agreement_ratio >= ENSEMBLE_AGREEMENT_THRESHOLD:
        ensemble_confidence = most_common_label
    else:
        # Worst-case: pick the label with the lowest rank
        ensemble_confidence = min(confidences, key=lambda c: _CONFIDENCE_RANK.get(c, 0))

    # Herd moments: collect from all runs, count occurrences
    # Herd moments are strings, so we deduplicate by content
    herd_counter: Counter[str] = Counter()
    for r in runs:
        if r.decision_summary and r.decision_summary.herd_moments:
            for moment in r.decision_summary.herd_moments:
                herd_counter[moment] += 1

    robust_herds = [m for m, count in herd_counter.items() if count >= ROBUST_HERD_MOMENT_THRESHOLD]
    noisy_herds = [m for m, count in herd_counter.items() if count < ROBUST_HERD_MOMENT_THRESHOLD]

    return {
        "aggregate_distribution": [round(a, 4) for a in aggregates],
        "confidence_distribution": confidences,
        "agreement_ratio": round(agreement_ratio, 4),
        "ensemble_confidence": ensemble_confidence,
        "robust_herd_moments": robust_herds,
        "noisy_herd_moments": noisy_herds,
    }


async def run_ensemble(
    prompt: str,
    llm: LLMClient,
    ensemble_size: int = DEFAULT_ENSEMBLE_SIZE,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    document_text: str | None = None,
    document_name: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
) -> EnsembleResult:
    """Run N simulations of the same scenario for ensemble robustness.

    Agent generation happens once. Only the engine tick loop repeats per run.
    Runs execute sequentially to avoid overwhelming local LLM providers.
    """
    logger.info(
        "Ensemble started prompt=%r ensemble_size=%d",
        prompt[:60] + ("..." if len(prompt) > 60 else ""), ensemble_size,
    )

    # Resolve preset + explicit overrides
    preset_vals = resolve_preset(preset)
    final_agents = agent_count or preset_vals.get("agent_count")
    final_ticks = tick_count or preset_vals.get("tick_count")

    # Optional document grounding (once, shared across runs)
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

    # Analyze scenario ONCE
    blueprint = await analyze_scenario(
        prompt, llm=llm, context=enriched_context or None,
        agent_count=final_agents, tick_count=final_ticks,
    )

    # Generate agents ONCE — shared across all runs
    agents = await generate_agents(blueprint, llm=llm)

    has_grounding = bool(grounding)
    completed_runs: list[RunResultWithInsights] = []

    # Run N simulations sequentially
    for run_num in range(1, ensemble_size + 1):
        logger.info("Ensemble run %d/%d started", run_num, ensemble_size)

        engine = SimulationEngine(
            blueprint=blueprint, agents=agents, llm=llm,
            grounding_context=grounding_text,
        )
        ticks = await engine.run()

        run_id = generate_run_id(prefix=f"ensemble-r{run_num}")
        result = build_run_result(prompt, blueprint, agents, ticks, run_id=run_id)

        decision_summary = await generate_decision_summary(
            result, engine.influence_graph, llm, has_grounding=has_grounding,
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
        completed_runs.append(enriched)

        logger.info(
            "Ensemble run %d/%d complete aggregate=%.3f confidence=%s",
            run_num, ensemble_size,
            result.summary.final_aggregate_stance,
            decision_summary.confidence if decision_summary else "?",
        )

    # Aggregate ensemble metrics
    metrics = _aggregate_ensemble(completed_runs)

    ensemble_result = EnsembleResult(
        ensemble_size=ensemble_size,
        runs=completed_runs,
        primary_run=completed_runs[0] if completed_runs else None,
        decision_summary=completed_runs[0].decision_summary if completed_runs else None,
        **metrics,
    )

    # Save to disk
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    ensemble_id = generate_run_id(prefix="ensemble")
    (runs_path / f"{ensemble_id}.json").write_text(
        ensemble_result.model_dump_json(indent=2, by_alias=True)
    )

    logger.info(
        "Ensemble complete runs=%d agreement=%.0f%% confidence=%s aggregates=%s",
        ensemble_size,
        metrics["agreement_ratio"] * 100,
        metrics["ensemble_confidence"],
        metrics["aggregate_distribution"],
    )

    return ensemble_result


async def stream_ensemble(
    prompt: str,
    llm: LLMClient,
    ensemble_size: int = DEFAULT_ENSEMBLE_SIZE,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
    fast_llm: LLMClient | None = None,
    document_text: str | None = None,
    document_name: str | None = None,
    agent_count: int | None = None,
    tick_count: int | None = None,
    preset: str | None = None,
):
    """Async generator streaming SSE-ready dicts for an ensemble run.

    Emits:
      - thinking
      - grounding (if applicable)
      - blueprint
      - scenario (agents, once — shared across runs)
      - run_start (per run)
      - tick (per tick of the active run)
      - run_complete (per run, carries the full RunResultWithInsights)
      - done (final EnsembleResult)

    The UI can drive the Arena off `tick` events exactly the way it does for a
    single simulate stream — it just gets N ×  tick-count tick events plus
    run_start boundaries so the active-run selector updates live.
    """
    logger.info(
        "Ensemble stream started prompt=%r ensemble_size=%d",
        prompt[:60] + ("..." if len(prompt) > 60 else ""), ensemble_size,
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

    # Analyze scenario ONCE
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
            "ensemble_size": ensemble_size,
        },
    }

    # Generate agents ONCE — shared across all runs. This mirrors the
    # non-streaming run_ensemble — all N runs share the same cast.
    agents = await generate_agents(blueprint, llm=llm)

    # Import AgentInfo locally to keep the module surface small.
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
            "ensemble_size": ensemble_size,
        },
    }

    has_grounding = bool(grounding)
    completed_runs: list[RunResultWithInsights] = []

    for run_num in range(1, ensemble_size + 1):
        logger.info("Ensemble stream run %d/%d started", run_num, ensemble_size)
        yield {
            "type": "run_start",
            "data": {"run_number": run_num, "ensemble_size": ensemble_size},
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

        run_id = generate_run_id(prefix=f"ensemble-r{run_num}")
        result = build_run_result(prompt, blueprint, agents, tick_records, run_id=run_id)

        decision_summary = await generate_decision_summary(
            result, engine.influence_graph, llm, has_grounding=has_grounding,
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
        completed_runs.append(enriched)

        logger.info(
            "Ensemble stream run %d/%d complete aggregate=%.3f confidence=%s",
            run_num, ensemble_size,
            result.summary.final_aggregate_stance,
            decision_summary.confidence if decision_summary else "?",
        )
        yield {
            "type": "run_complete",
            "data": {
                "run_number": run_num,
                "run": enriched.model_dump(mode="json"),
            },
        }

    # Aggregate ensemble metrics
    metrics = _aggregate_ensemble(completed_runs)

    ensemble_result = EnsembleResult(
        ensemble_size=ensemble_size,
        runs=completed_runs,
        primary_run=completed_runs[0] if completed_runs else None,
        decision_summary=completed_runs[0].decision_summary if completed_runs else None,
        **metrics,
    )

    # Save to disk
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    ensemble_id = generate_run_id(prefix="ensemble")
    (runs_path / f"{ensemble_id}.json").write_text(
        ensemble_result.model_dump_json(indent=2, by_alias=True)
    )

    logger.info(
        "Ensemble stream complete runs=%d agreement=%.0f%% confidence=%s",
        ensemble_size,
        metrics["agreement_ratio"] * 100,
        metrics["ensemble_confidence"],
    )

    yield {"type": "done", "data": ensemble_result.model_dump(mode="json")}
