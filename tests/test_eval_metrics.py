"""Tests for deterministic run metrics."""

from pythia.eval_metrics import (
    PARSE_FAILURE_REASONING,
    parse_failure_rate,
    run_metrics,
    stance_volatility,
    target_validity_rate,
    verdict_direction,
)
from pythia.models import (
    AgentInfo, BiggestShift, RunResult, RunSummary, ScenarioInfo, TickEvent, TickRecord,
)


def _event(agent_id, prev, stance, reasoning="ok", target=None):
    return TickEvent(
        agent_id=agent_id, stance=stance, previous_stance=prev, action="hold",
        emotion="calm", reasoning=reasoning, message="m", influence_target=target,
    )


def _result(ticks):
    agents = [
        AgentInfo(id=a, name=a, role="r", persona="p", bias="anchoring", initial_stance=0.5)
        for a in ("a", "b")
    ]
    return RunResult(
        run_id="run-test",
        scenario=ScenarioInfo(input="q", type="t", title="T", stance_spectrum=["1", "2", "3", "4", "5"]),
        agents=agents,
        ticks=ticks,
        summary=RunSummary(
            total_ticks=len(ticks), final_aggregate_stance=ticks[-1].aggregate_stance,
            biggest_shift=BiggestShift(agent_id="a", from_stance=0.5, to_stance=0.4, reason="x"),
            consensus_reached=False,
        ),
    )


def test_parse_failure_rate_counts_fallback_events():
    r = _result([
        TickRecord(tick=1, aggregate_stance=0.5, events=[
            _event("a", 0.5, 0.5, reasoning=PARSE_FAILURE_REASONING),
            _event("b", 0.5, 0.4),
        ]),
    ])
    assert parse_failure_rate(r) == 0.5


def test_target_validity_rate_ignores_events_without_target():
    r = _result([
        TickRecord(tick=1, aggregate_stance=0.5, events=[
            _event("a", 0.5, 0.5, target="b"),
            _event("b", 0.5, 0.4, target="ghost"),
        ]),
        TickRecord(tick=2, aggregate_stance=0.5, events=[_event("a", 0.5, 0.5)]),
    ])
    assert target_validity_rate(r) == 0.5


def test_target_validity_rate_is_one_when_no_targets():
    r = _result([TickRecord(tick=1, aggregate_stance=0.5, events=[_event("a", 0.5, 0.5)])])
    assert target_validity_rate(r) == 1.0


def test_stance_volatility_is_mean_absolute_delta():
    r = _result([
        TickRecord(tick=1, aggregate_stance=0.5, events=[_event("a", 0.5, 0.3), _event("b", 0.5, 0.6)]),
    ])
    assert abs(stance_volatility(r) - 0.15) < 1e-9


def test_verdict_direction_bands():
    assert verdict_direction(0.30) == "sell"
    assert verdict_direction(0.55) == "neutral"
    assert verdict_direction(0.61) == "buy"


def test_run_metrics_keys():
    r = _result([TickRecord(tick=1, aggregate_stance=0.3, events=[_event("a", 0.5, 0.3)])])
    m = run_metrics(r)
    assert set(m) == {"parse_failure_rate", "target_validity_rate", "stance_volatility", "final_aggregate", "direction"}
    assert m["direction"] == "sell"
    assert m["final_aggregate"] == 0.3
