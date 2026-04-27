"""Shared run summary computation — single source of truth for both orchestrator and oracle loop."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pythia.models import (
    Agent,
    AgentInfo,
    BiggestShift,
    RunResult,
    RunSummary,
    ScenarioBlueprint,
    ScenarioInfo,
    TickRecord,
)


def generate_run_id(prefix: str = "run") -> str:
    """Generate a collision-safe run ID with second precision + UUID suffix."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6]
    return f"{prefix}_{now.strftime('%Y-%m-%d_%H%M%S')}_{short_uuid}"


def compute_summary(ticks: list[TickRecord], agents: list[Agent] | list[AgentInfo]) -> RunSummary:
    """Compute run summary from ticks and agents.

    Works with both Agent objects (from generator) and AgentInfo objects (from results).
    """
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


def build_run_result(
    prompt: str,
    blueprint: ScenarioBlueprint,
    agents: list[Agent],
    ticks: list[TickRecord],
    run_id: str | None = None,
) -> RunResult:
    """Build a RunResult from simulation components. Used by both orchestrator and oracle loop."""
    if run_id is None:
        run_id = generate_run_id()

    agent_infos = [
        AgentInfo(
            id=a.id, name=a.name, role=a.role,
            persona=a.persona, bias=a.bias,
            initial_stance=a.initial_stance,
        )
        for a in agents
    ]

    summary = compute_summary(ticks, agents)

    return RunResult(
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
