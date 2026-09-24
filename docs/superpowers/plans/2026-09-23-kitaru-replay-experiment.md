# Kitaru Replay Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record Pythia simulations as Kitaru sessions, replay them with the agent-tick model swapped (Groq 8B → OpenAI gpt-4o-mini) against an unchanged-replay noise floor, score both arms, and produce an evidence-based feedback memo for Kitaru's CTO by Fri 2026-09-25.

**Architecture:** A `RecordingLLMClient` wraps Pythia's existing `LLMClient` protocol and reports every call to a `SessionRecorder` (a Protocol we own). A Kitaru-backed recorder implements that Protocol with the Kitaru SDK; a fake implements it in tests. A small `experiment` module runs the pipeline (analyze → generate → engine → evaluate) with separate `main` / `tick` / `judge` clients and computes deterministic metrics from `eval_metrics`. Scripts drive recording, replay, and reporting. The engine, orchestrator, and API are untouched.

**Tech Stack:** Python 3.11, pytest + pytest-asyncio, httpx, Kitaru SDK (`kitaru` package, managed cloud), Groq + OpenAI via existing clients.

**Spec:** `docs/superpowers/specs/2026-09-23-kitaru-replay-experiment-design.md`

## Global Constraints

- Branch: `exp/kitaru-replay`, created from `origin/main`.
- Kitaru is an optional dependency: `pyproject.toml` extra `kitaru`; `import kitaru` only inside `src/pythia/kitaru_recorder.py`, guarded.
- Engine, orchestrator, and API code paths must not change behaviour; the existing backend suite (307 tests) stays green.
- Credentials only from environment (`.env`): `GROQ_API_KEY`, `OPENAI_API_KEY`, and whatever Kitaru's cloud login provides. Never log or commit secrets.
- Client roles (replaces the spec's per-stage tags, because one client serves analyze/generate/decision): `main` (Groq `llama-3.3-70b-versatile`), `tick` (Groq `llama-3.1-8b-instant`), `judge` (Groq `llama-3.3-70b-versatile`). Replay overrides apply to `tick` only.
- Cohort: 5 README prompts × 2 runs = 10 sessions; `agent_count=5`, `tick_count=8`.
- Friction log (`docs/kitaru/friction-log.md`) is updated in every task that hits friction; entry format fixed in Task 1.

---

### Task 1: Spike — Kitaru setup, API notes, friction log

This task produces knowledge, not product code. Its outputs are the two documents later tasks depend on.

**Files:**
- Create: `docs/kitaru/api-notes.md`
- Create: `docs/kitaru/friction-log.md`
- Modify: `pyproject.toml` (add optional extra)

**Interfaces:**
- Produces: `docs/kitaru/api-notes.md` with a filled **SDK mapping table** (below) that Task 5 codes against.

- [ ] **Step 1: Sync main, create the branch**

```bash
git fetch origin
git checkout main && git pull --ff-only origin main
git checkout -b exp/kitaru-replay
```

- [ ] **Step 2: Add the optional dependency and install**

In `pyproject.toml`, under `[project.optional-dependencies]` add:

```toml
kitaru = [
    "kitaru[cli,worker,mcp]",
]
```

Run:

```bash
pip install -e ".[dev,kitaru]"
kitaru login
```

Expected: login opens the managed-cloud flow and succeeds. Record wall-clock time from `pip install` to successful login.

- [ ] **Step 3: Create the friction log with its entry format**

Create `docs/kitaru/friction-log.md`:

```markdown
# Kitaru friction log

Every time something breaks, the docs don't answer the question, or a workaround is needed, add an entry. The memo is built from this file.

| When (UTC) | Area | What we tried | What happened | Time lost | Severity | Suggested fix |
|---|---|---|---|---|---|---|
```

Severity is one of `blocker`, `major`, `minor`. Add a row now for anything that happened in Step 2.

- [ ] **Step 4: Find the five SDK capabilities we need**

Using the docs (`https://docs.zenml.io/kitaru/adapters/custom.md`, `.../core-concepts/agents-and-sessions.md`, `.../guides/replay-and-overrides.md`, `.../guides/write-an-evaluator.md`, `.../guides/llm-calls.md`), the `kitaru-adapter-builder` skill from `https://github.com/zenml-io/kitaru-skills`, and the PydanticAI adapter source as reference, determine the exact calls for:

1. Start a session for agent `pythia-simulation` with an input payload.
2. Record one LLM-call node (requested model, served model, request, response, latency, tokens) on the current session.
3. Finish a session with an output payload.
4. During a replay, read the override for a model boundary (so we can swap the `tick` client).
5. Write an evaluation result (name, version, numeric value, per session).

Also determine: how a worker invokes our code for replay (entrypoint registration), and whether replay can target a subset of LLM calls.

- [ ] **Step 5: Write `docs/kitaru/api-notes.md`**

```markdown
# Kitaru API notes (spike, 2026-09-23)

Kitaru version: <output of `pip show kitaru | grep Version`>

## SDK mapping table

| Capability | Exact call (module.function / method + signature) | Sync or async | Notes |
|---|---|---|---|
| start_session | | | |
| record_llm_call | | | |
| finish_session | | | |
| read_override | | | |
| write_evaluation | | | |

## Replay entrypoint
How a worker calls our code, and what we must register.

## Can replay swap only the tick model?
Yes / no, with evidence.

## Decision: replay path
- Path A (native): Kitaru replays sessions and our wrapper applies overrides.
- Path B (fallback): our script re-runs the cohort prompts with the override and records new sessions tagged by arm; Kitaru is used for cohorts, evaluations, and comparison only.
Chosen path and why:
```

Fill every cell. If a capability does not exist, write "not supported" and add a friction-log row with severity.

- [ ] **Step 6: Prove recording works with a throwaway script**

Create `scratch_kitaru_hello.py` (not committed) that starts a session, records one fake LLM-call node, and finishes it, using the calls from the table. Run it and confirm the session appears in the Kitaru dashboard with one LLM-call node.

Gate: if this fails by end of day Wed 2026-09-23, stop, log a `blocker` row, and tell the user the memo pivots to setup friction plus a reduced scope.

- [ ] **Step 7: Commit**

```bash
rm -f scratch_kitaru_hello.py
git add pyproject.toml docs/kitaru/api-notes.md docs/kitaru/friction-log.md
git commit -m "chore(kitaru): add optional dependency, API notes, friction log"
```

---

### Task 2: Deterministic run metrics

Pure functions over a finished run. Reused later by the backend plan (parse-failure counting).

**Files:**
- Create: `src/pythia/eval_metrics.py`
- Test: `tests/test_eval_metrics.py`

**Interfaces:**
- Consumes: `pythia.models.RunResult`, `TickRecord`, `TickEvent`, `AgentInfo`
- Produces:
  - `PARSE_FAILURE_REASONING: str = "Failed to parse response"`
  - `parse_failure_rate(result: RunResult) -> float`
  - `target_validity_rate(result: RunResult) -> float`
  - `stance_volatility(result: RunResult) -> float`
  - `verdict_direction(stance: float, neutral_band: float = 0.1) -> Literal["buy", "sell", "neutral"]`
  - `run_metrics(result: RunResult) -> dict[str, float | str]` with keys `parse_failure_rate`, `target_validity_rate`, `stance_volatility`, `final_aggregate`, `direction`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_eval_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.eval_metrics'`

- [ ] **Step 3: Implement**

```python
"""Deterministic metrics over a finished run. No LLM calls."""

from __future__ import annotations

from typing import Literal

from pythia.models import RunResult

# Must match the fallback reasoning string in SimulationEngine._run_agent_tick.
PARSE_FAILURE_REASONING = "Failed to parse response"


def _events(result: RunResult):
    for tick in result.ticks:
        yield from tick.events


def parse_failure_rate(result: RunResult) -> float:
    events = list(_events(result))
    if not events:
        return 0.0
    failed = sum(1 for e in events if e.reasoning == PARSE_FAILURE_REASONING)
    return failed / len(events)


def target_validity_rate(result: RunResult) -> float:
    agent_ids = {a.id for a in result.agents}
    targeted = [e for e in _events(result) if e.influence_target]
    if not targeted:
        return 1.0
    return sum(1 for e in targeted if e.influence_target in agent_ids) / len(targeted)


def stance_volatility(result: RunResult) -> float:
    events = list(_events(result))
    if not events:
        return 0.0
    return sum(abs(e.stance - e.previous_stance) for e in events) / len(events)


def verdict_direction(stance: float, neutral_band: float = 0.1) -> Literal["buy", "sell", "neutral"]:
    if stance > 0.5 + neutral_band:
        return "buy"
    if stance < 0.5 - neutral_band:
        return "sell"
    return "neutral"


def run_metrics(result: RunResult) -> dict[str, float | str]:
    final = result.summary.final_aggregate_stance
    return {
        "parse_failure_rate": parse_failure_rate(result),
        "target_validity_rate": target_validity_rate(result),
        "stance_volatility": stance_volatility(result),
        "final_aggregate": final,
        "direction": verdict_direction(final),
    }
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_eval_metrics.py -v`
Expected: 6 passed.

- [ ] **Step 5: Confirm the fallback string still matches the engine**

Run: `grep -n "Failed to parse response" src/pythia/engine.py`
Expected: one match inside `_run_agent_tick`. If the string differs, update `PARSE_FAILURE_REASONING`.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/eval_metrics.py tests/test_eval_metrics.py
git commit -m "feat(eval): deterministic run metrics"
```

---

### Task 3: RecordingLLMClient

**Files:**
- Create: `src/pythia/recording.py`
- Modify: `src/pythia/llm.py` (append `parse_model_spec`; the backend plan reuses it)
- Test: `tests/test_recording.py`

**Interfaces:**
- Consumes: `pythia.llm.LLMClient` (protocol: `async generate(prompt, system=None, seed=None) -> dict`), `pythia.llm.build_llm_client(provider, ollama_url, model)`
- Produces:
  - `class SessionRecorder(Protocol)` with `record_llm_call(*, role: str, requested_model: str, model: str, system: str | None, prompt: str, response: dict, latency_ms: int) -> None` and `override_for(role: str) -> str | None`
  - `class NullRecorder` (no-op implementation)
  - `pythia.llm.parse_model_spec(spec: str) -> tuple[str, str]` for `"provider:model"` (re-exported from `pythia.recording`)
  - `class RecordingLLMClient(inner: LLMClient, role: str, recorder: SessionRecorder, factory: Callable[[str], LLMClient] | None = None)` with `async generate(...)`, `model` property, `provider_name` property, `async close()`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the recording LLM wrapper."""

import pytest

from pythia.recording import NullRecorder, RecordingLLMClient, parse_model_spec
from tests.conftest import FakeLLMClient


class FakeRecorder:
    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def record_llm_call(self, **kw):
        self.calls.append(kw)

    def override_for(self, role):
        return self.overrides.get(role)


def _inner(response, model="inner-model"):
    c = FakeLLMClient(responses=[response])
    c.model = model
    c.provider_name = "fake"
    return c


async def test_delegates_and_records():
    inner = _inner({"ok": 1})
    rec = FakeRecorder()
    client = RecordingLLMClient(inner, role="tick", recorder=rec)
    out = await client.generate("hello", system="sys")
    assert out == {"ok": 1}
    assert len(rec.calls) == 1
    call = rec.calls[0]
    assert call["role"] == "tick"
    assert call["requested_model"] == "inner-model"
    assert call["model"] == "inner-model"
    assert call["prompt"] == "hello" and call["system"] == "sys"
    assert call["response"] == {"ok": 1}
    assert call["latency_ms"] >= 0


async def test_override_routes_to_factory_client_for_matching_role_only():
    inner = _inner({"from": "inner"})
    alt = _inner({"from": "alt"}, model="gpt-4o-mini")
    built = []

    def factory(spec):
        built.append(spec)
        return alt

    rec = FakeRecorder(overrides={"tick": "openai:gpt-4o-mini"})
    tick = RecordingLLMClient(inner, role="tick", recorder=rec, factory=factory)
    main = RecordingLLMClient(_inner({"from": "main"}), role="main", recorder=rec, factory=factory)

    assert await tick.generate("p") == {"from": "alt"}
    assert await main.generate("p") == {"from": "main"}
    assert built == ["openai:gpt-4o-mini"]
    assert rec.calls[0]["requested_model"] == "inner-model"
    assert rec.calls[0]["model"] == "gpt-4o-mini"


async def test_override_client_is_built_once():
    alt = FakeLLMClient(responses=[{"a": 1}, {"a": 2}])
    alt.model = "gpt-4o-mini"
    count = []

    def factory(spec):
        count.append(spec)
        return alt

    rec = FakeRecorder(overrides={"tick": "openai:gpt-4o-mini"})
    client = RecordingLLMClient(_inner({}), role="tick", recorder=rec, factory=factory)
    await client.generate("1")
    await client.generate("2")
    assert len(count) == 1


async def test_null_recorder_is_transparent():
    client = RecordingLLMClient(_inner({"x": 1}), role="main", recorder=NullRecorder())
    assert await client.generate("p") == {"x": 1}


def test_parse_model_spec():
    assert parse_model_spec("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")
    with pytest.raises(ValueError):
        parse_model_spec("gpt-4o-mini")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_recording.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.recording'`

- [ ] **Step 3: Implement**

```python
"""LLM wrapper that reports every call to a session recorder and applies replay overrides."""

from __future__ import annotations

import logging
import time
from typing import Callable, Protocol

from pythia.llm import LLMClient, build_llm_client, parse_model_spec

logger = logging.getLogger(__name__)

__all__ = ["NullRecorder", "RecordingLLMClient", "SessionRecorder", "parse_model_spec"]


class SessionRecorder(Protocol):
    def record_llm_call(
        self, *, role: str, requested_model: str, model: str,
        system: str | None, prompt: str, response: dict, latency_ms: int,
    ) -> None: ...

    def override_for(self, role: str) -> str | None: ...


class NullRecorder:
    def record_llm_call(self, **_: object) -> None:
        return None

    def override_for(self, role: str) -> str | None:
        return None


def _default_factory(spec: str) -> LLMClient:
    provider, model = parse_model_spec(spec)
    return build_llm_client(provider=provider, model=model)


class RecordingLLMClient:
    """Implements LLMClient. Delegates to `inner`, or to an override client for this role."""

    def __init__(
        self,
        inner: LLMClient,
        role: str,
        recorder: SessionRecorder,
        factory: Callable[[str], LLMClient] | None = None,
    ):
        self.inner = inner
        self.role = role
        self.recorder = recorder
        self._factory = factory or _default_factory
        self._override_spec: str | None = None
        self._override_client: LLMClient | None = None

    @property
    def model(self) -> str:
        return getattr(self.inner, "model", "unknown")

    @property
    def provider_name(self) -> str:
        return getattr(self.inner, "provider_name", "unknown")

    def _target(self) -> LLMClient:
        spec = self.recorder.override_for(self.role)
        if not spec:
            return self.inner
        if spec != self._override_spec:
            logger.info("Replay override role=%s spec=%s", self.role, spec)
            self._override_client = self._factory(spec)
            self._override_spec = spec
        return self._override_client  # type: ignore[return-value]

    async def generate(self, prompt: str, system: str | None = None, seed: int | None = None) -> dict:
        target = self._target()
        t0 = time.perf_counter()
        response = await target.generate(prompt=prompt, system=system, seed=seed)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        self.recorder.record_llm_call(
            role=self.role,
            requested_model=self.model,
            model=getattr(target, "model", "unknown"),
            system=system,
            prompt=prompt,
            response=response,
            latency_ms=latency_ms,
        )
        return response

    async def close(self) -> None:
        for client in (self.inner, self._override_client):
            close = getattr(client, "close", None)
            if close:
                await close()
```

Also append to `src/pythia/llm.py`:

```python
def parse_model_spec(spec: str) -> tuple[str, str]:
    """Split "provider:model" into its parts."""
    provider, sep, model = spec.partition(":")
    if not sep or not provider or not model:
        raise ValueError(f"Model spec must look like 'provider:model', got {spec!r}")
    return provider, model
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_recording.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full suite (nothing else may change)**

Run: `python3 -m pytest -q`
Expected: all previous tests plus the new ones pass.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/recording.py src/pythia/llm.py tests/test_recording.py
git commit -m "feat(kitaru): recording LLM wrapper with per-role replay overrides"
```

---

### Task 4: Experiment pipeline runner

Runs one simulation with separate `main`, `tick`, and `judge` clients and returns everything the scripts need. `run_simulation` is not reused because it has no `fast_llm` parameter and adds a decision-summary call we don't need.

**Files:**
- Create: `src/pythia/experiment.py`
- Test: `tests/test_experiment.py`

**Interfaces:**
- Consumes: `analyze_scenario(prompt, llm, context=None, agent_count=None, tick_count=None)`, `generate_agents(blueprint, llm)`, `SimulationEngine(blueprint, agents, llm, grounding_context=None).run()`, `build_run_result(prompt, blueprint, agents, ticks)`, `evaluate_run(run_result, agents, llm)`, `run_metrics(result)` (Task 2)
- Produces:
  - `@dataclass ExperimentRun(prompt: str, result: RunResult, evaluations: list[AgentEvaluation], metrics: dict[str, float | str])` with property `coherence_rate: float`
  - `async def run_experiment_once(prompt: str, main_llm: LLMClient, tick_llm: LLMClient, judge_llm: LLMClient, agent_count: int = 5, tick_count: int = 8) -> ExperimentRun`
  - `README_PROMPTS: list[str]` (the 5 cohort prompts)

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the experiment runner wiring (pipeline stages are patched)."""

from types import SimpleNamespace

import pytest

import pythia.experiment as exp
from pythia.models import AgentEvaluation


async def test_run_experiment_once_wires_clients_and_metrics(monkeypatch):
    seen = {}

    async def fake_analyze(prompt, llm, context=None, agent_count=None, tick_count=None):
        seen["analyze"] = (llm, agent_count, tick_count)
        return SimpleNamespace(tick_count=tick_count)

    async def fake_generate(blueprint, llm):
        seen["generate"] = llm
        return [SimpleNamespace(id="a")]

    class FakeEngine:
        def __init__(self, blueprint, agents, llm, grounding_context=None):
            seen["engine"] = llm

        async def run(self):
            return ["tick"]

    fake_result = SimpleNamespace(summary=SimpleNamespace(final_aggregate_stance=0.3))

    monkeypatch.setattr(exp, "analyze_scenario", fake_analyze)
    monkeypatch.setattr(exp, "generate_agents", fake_generate)
    monkeypatch.setattr(exp, "SimulationEngine", FakeEngine)
    monkeypatch.setattr(exp, "build_run_result", lambda p, b, a, t: fake_result)

    async def fake_eval(result, agents, llm):
        seen["judge"] = llm
        return [AgentEvaluation(agent_id="a", is_coherent=True), AgentEvaluation(agent_id="b", is_coherent=False)]

    monkeypatch.setattr(exp, "evaluate_run", fake_eval)
    monkeypatch.setattr(exp, "run_metrics", lambda r: {"direction": "sell"})

    main, tick, judge = object(), object(), object()
    run = await exp.run_experiment_once("q", main, tick, judge, agent_count=5, tick_count=8)

    assert seen["analyze"] == (main, 5, 8)
    assert seen["generate"] is main
    assert seen["engine"] is tick
    assert seen["judge"] is judge
    assert run.metrics == {"direction": "sell"}
    assert run.coherence_rate == 0.5


def test_readme_prompts_has_five():
    assert len(exp.README_PROMPTS) == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_experiment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.experiment'`

- [ ] **Step 3: Implement**

```python
"""Single-run experiment pipeline with separate main / tick / judge clients."""

from __future__ import annotations

from dataclasses import dataclass

from pythia.analyzer import analyze_scenario
from pythia.engine import SimulationEngine
from pythia.eval_metrics import run_metrics
from pythia.evaluator import evaluate_run
from pythia.generator import generate_agents
from pythia.llm import LLMClient
from pythia.models import AgentEvaluation, RunResult
from pythia.summary import build_run_result

README_PROMPTS = [
    "Should our startup adopt AI coding tools for all engineering tasks?",
    "Should we raise a Series A or stay bootstrapped?",
    "Should a city ban single-use plastics in restaurants?",
    "Should tech companies mandate a return to office 5 days a week?",
    "Should a social media platform ban political advertising entirely?",
]


@dataclass
class ExperimentRun:
    prompt: str
    result: RunResult
    evaluations: list[AgentEvaluation]
    metrics: dict[str, float | str]

    @property
    def coherence_rate(self) -> float:
        if not self.evaluations:
            return 0.0
        return sum(1 for e in self.evaluations if e.is_coherent) / len(self.evaluations)


async def run_experiment_once(
    prompt: str,
    main_llm: LLMClient,
    tick_llm: LLMClient,
    judge_llm: LLMClient,
    agent_count: int = 5,
    tick_count: int = 8,
) -> ExperimentRun:
    blueprint = await analyze_scenario(
        prompt, llm=main_llm, agent_count=agent_count, tick_count=tick_count,
    )
    agents = await generate_agents(blueprint, llm=main_llm)
    engine = SimulationEngine(blueprint=blueprint, agents=agents, llm=tick_llm)
    ticks = await engine.run()
    result = build_run_result(prompt, blueprint, agents, ticks)
    evaluations = await evaluate_run(result, agents, judge_llm)
    return ExperimentRun(prompt=prompt, result=result, evaluations=evaluations, metrics=run_metrics(result))
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_experiment.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/experiment.py tests/test_experiment.py
git commit -m "feat(kitaru): experiment runner with separate main/tick/judge clients"
```

---

### Task 5: Kitaru recorder and cohort recording

**Files:**
- Create: `src/pythia/kitaru_recorder.py`
- Create: `scripts/kitaru_record.py`
- Test: `tests/test_kitaru_recorder.py`

**Interfaces:**
- Consumes: SDK mapping table in `docs/kitaru/api-notes.md` (Task 1), `SessionRecorder` + `RecordingLLMClient` (Task 3), `run_experiment_once` + `README_PROMPTS` (Task 4)
- Produces:
  - `class KitaruRecorder` implementing `SessionRecorder`, plus `start(input: dict, tags: dict[str, str]) -> str` (returns session id), `finish(output: dict) -> None`, `write_evaluations(session_id: str, values: dict[str, float]) -> None`, and constructor `KitaruRecorder(agent_name: str = "pythia-simulation", overrides: dict[str, str] | None = None, sdk: KitaruSDK | None = None)`
  - `class KitaruSDK(Protocol)` with the five capabilities as methods: `start_session(agent: str, input: dict, tags: dict) -> str`, `record_llm_call(session_id: str, node: dict) -> None`, `finish_session(session_id: str, output: dict) -> None`, `read_override(role: str) -> str | None`, `write_evaluation(session_id: str, name: str, value: float) -> None`
  - `def real_sdk() -> KitaruSDK` (the only place that imports `kitaru`)
  - JSONL cohort manifest at `data/kitaru/cohort.jsonl`, one line per session: `{"session_id", "prompt", "repeat", "arm", "metrics", "coherence_rate"}`

- [ ] **Step 1: Write the failing tests (against a fake SDK)**

```python
"""Tests for KitaruRecorder using a fake SDK."""

from pythia.kitaru_recorder import KitaruRecorder


class FakeSDK:
    def __init__(self, override=None):
        self.started, self.nodes, self.finished, self.evals = [], [], [], []
        self.override = override or {}

    def start_session(self, agent, input, tags):
        self.started.append((agent, input, tags))
        return "sess-1"

    def record_llm_call(self, session_id, node):
        self.nodes.append((session_id, node))

    def finish_session(self, session_id, output):
        self.finished.append((session_id, output))

    def read_override(self, role):
        return self.override.get(role)

    def write_evaluation(self, session_id, name, value):
        self.evals.append((session_id, name, value))


def test_records_nodes_on_current_session():
    sdk = FakeSDK()
    rec = KitaruRecorder(sdk=sdk)
    sid = rec.start({"prompt": "q"}, tags={"arm": "baseline"})
    rec.record_llm_call(role="tick", requested_model="m", model="m", system=None, prompt="p", response={"a": 1}, latency_ms=5)
    rec.finish({"final": 0.3})
    assert sid == "sess-1"
    assert sdk.started == [("pythia-simulation", {"prompt": "q"}, {"arm": "baseline"})]
    node = sdk.nodes[0][1]
    assert sdk.nodes[0][0] == "sess-1"
    assert node["role"] == "tick" and node["latency_ms"] == 5 and node["response"] == {"a": 1}
    assert sdk.finished == [("sess-1", {"final": 0.3})]


def test_explicit_overrides_win_over_sdk():
    sdk = FakeSDK(override={"tick": "groq:llama-3.1-8b-instant"})
    rec = KitaruRecorder(sdk=sdk, overrides={"tick": "openai:gpt-4o-mini"})
    assert rec.override_for("tick") == "openai:gpt-4o-mini"
    assert KitaruRecorder(sdk=sdk).override_for("tick") == "groq:llama-3.1-8b-instant"
    assert KitaruRecorder(sdk=sdk).override_for("main") is None


def test_write_evaluations():
    sdk = FakeSDK()
    rec = KitaruRecorder(sdk=sdk)
    rec.write_evaluations("sess-1", {"coherence_rate": 0.8, "parse_failure_rate": 0.0})
    assert ("sess-1", "coherence_rate", 0.8) in sdk.evals
    assert len(sdk.evals) == 2


def test_recording_before_start_raises():
    rec = KitaruRecorder(sdk=FakeSDK())
    try:
        rec.record_llm_call(role="tick", requested_model="m", model="m", system=None, prompt="p", response={}, latency_ms=1)
    except RuntimeError as exc:
        assert "start" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_kitaru_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the recorder**

The `KitaruRecorder` class is SDK-agnostic. `real_sdk()` is the only Kitaru-specific code: implement each of its five methods with the exact call from the api-notes mapping table (one call per method). If `read_override` is "not supported" (Path B), make it return `None`.

```python
"""Kitaru-backed SessionRecorder. The only module that imports kitaru."""

from __future__ import annotations

from typing import Protocol


class KitaruSDK(Protocol):
    def start_session(self, agent: str, input: dict, tags: dict) -> str: ...
    def record_llm_call(self, session_id: str, node: dict) -> None: ...
    def finish_session(self, session_id: str, output: dict) -> None: ...
    def read_override(self, role: str) -> str | None: ...
    def write_evaluation(self, session_id: str, name: str, value: float) -> None: ...


class KitaruRecorder:
    def __init__(
        self,
        agent_name: str = "pythia-simulation",
        overrides: dict[str, str] | None = None,
        sdk: KitaruSDK | None = None,
    ):
        self.agent_name = agent_name
        self.overrides = overrides or {}
        self.sdk = sdk or real_sdk()
        self.session_id: str | None = None

    def start(self, input: dict, tags: dict[str, str]) -> str:
        self.session_id = self.sdk.start_session(self.agent_name, input, tags)
        return self.session_id

    def finish(self, output: dict) -> None:
        if self.session_id is None:
            raise RuntimeError("finish() called before start()")
        self.sdk.finish_session(self.session_id, output)
        self.session_id = None

    def record_llm_call(
        self, *, role: str, requested_model: str, model: str,
        system: str | None, prompt: str, response: dict, latency_ms: int,
    ) -> None:
        if self.session_id is None:
            raise RuntimeError("record_llm_call() before start(): call start() first")
        self.sdk.record_llm_call(self.session_id, {
            "role": role, "requested_model": requested_model, "model": model,
            "system": system, "prompt": prompt, "response": response, "latency_ms": latency_ms,
        })

    def override_for(self, role: str) -> str | None:
        if role in self.overrides:
            return self.overrides[role]
        return self.sdk.read_override(role)

    def write_evaluations(self, session_id: str, values: dict[str, float]) -> None:
        for name, value in values.items():
            self.sdk.write_evaluation(session_id, name, float(value))


def real_sdk() -> KitaruSDK:
    """Adapter over the Kitaru SDK. Each method is one call from docs/kitaru/api-notes.md."""
    try:
        import kitaru  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Kitaru is not installed. Run: pip install -e '.[kitaru]'") from exc

    class _Real:
        # Replace each body with the exact call from the SDK mapping table.
        def start_session(self, agent, input, tags):
            raise NotImplementedError("fill from api-notes: start_session")

        def record_llm_call(self, session_id, node):
            raise NotImplementedError("fill from api-notes: record_llm_call")

        def finish_session(self, session_id, output):
            raise NotImplementedError("fill from api-notes: finish_session")

        def read_override(self, role):
            raise NotImplementedError("fill from api-notes: read_override")

        def write_evaluation(self, session_id, name, value):
            raise NotImplementedError("fill from api-notes: write_evaluation")

    return _Real()
```

Then replace the five `NotImplementedError` bodies in `_Real` with the calls recorded in the mapping table. None may remain before Step 6.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_kitaru_recorder.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the recording script**

```python
"""Record the cohort: 5 README prompts x 2 runs, baseline models, one Kitaru session each."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pythia.config import GROQ_FAST_MODEL, GROQ_MODEL
from pythia.experiment import README_PROMPTS, run_experiment_once
from pythia.kitaru_recorder import KitaruRecorder
from pythia.llm import build_llm_client
from pythia.logger import setup_logging
from pythia.recording import RecordingLLMClient

MANIFEST = Path("data/kitaru/cohort.jsonl")


async def record_one(prompt: str, repeat: int, arm: str, overrides: dict[str, str]) -> dict:
    recorder = KitaruRecorder(overrides=overrides)
    main = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_MODEL), "main", recorder)
    tick = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_FAST_MODEL), "tick", recorder)
    judge = RecordingLLMClient(build_llm_client(provider="groq", model=GROQ_MODEL), "judge", recorder)
    session_id = recorder.start({"prompt": prompt, "agent_count": 5, "tick_count": 8}, tags={"arm": arm, "repeat": str(repeat)})
    try:
        run = await run_experiment_once(prompt, main, tick, judge, agent_count=5, tick_count=8)
        recorder.finish({"final_aggregate": run.metrics["final_aggregate"], "direction": run.metrics["direction"]})
    finally:
        for c in (main, tick, judge):
            await c.close()
    numeric = {k: v for k, v in run.metrics.items() if isinstance(v, (int, float))}
    recorder.write_evaluations(session_id, {**numeric, "coherence_rate": run.coherence_rate})
    return {"session_id": session_id, "prompt": prompt, "repeat": repeat, "arm": arm,
            "metrics": run.metrics, "coherence_rate": run.coherence_rate}


async def main(arm: str, overrides: dict[str, str], repeats: int) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a") as fh:
        for prompt in README_PROMPTS:
            for repeat in range(repeats):
                row = await record_one(prompt, repeat, arm, overrides)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(f"{arm} repeat={repeat} session={row['session_id']} coherence={row['coherence_rate']:.2f} dir={row['metrics']['direction']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="recorded")
    ap.add_argument("--tick-model", default=None, help="provider:model override for the tick role")
    ap.add_argument("--repeats", type=int, default=2)
    args = ap.parse_args()
    setup_logging(level="INFO", log_dir="data/logs")
    asyncio.run(main(args.arm, {"tick": args.tick_model} if args.tick_model else {}, args.repeats))
```

- [ ] **Step 6: Record one session, check it, then the cohort**

```bash
python3 scripts/kitaru_record.py --arm smoke --repeats 1 2>&1 | head -3
```

Stop after the first line prints (Ctrl-C). Open the Kitaru dashboard: the session exists, carries tag `arm=smoke`, and has about 50 LLM-call nodes with roles `main`, `tick`, and `judge`. If not, fix `real_sdk()` and log friction.

Then delete the smoke line from `data/kitaru/cohort.jsonl` and record the cohort:

```bash
python3 scripts/kitaru_record.py --arm recorded --repeats 2
```

Expected: 10 lines printed, 10 sessions in the dashboard. Freeze them as a Kitaru cohort named `pythia-cohort-v1` (via the CLI or UI call noted in api-notes). Log friction.

- [ ] **Step 7: Commit**

```bash
git add src/pythia/kitaru_recorder.py scripts/kitaru_record.py tests/test_kitaru_recorder.py docs/kitaru/friction-log.md docs/kitaru/api-notes.md
git commit -m "feat(kitaru): Kitaru session recorder and cohort recording script"
```

---

### Task 6: Replay arms — noise floor and model swap

**Files:**
- Create: `scripts/kitaru_replay.py`
- Modify: `docs/kitaru/friction-log.md`

**Interfaces:**
- Consumes: `record_one(prompt, repeat, arm, overrides)` from `scripts/kitaru_record.py`, the Path A/B decision in api-notes, cohort `pythia-cohort-v1`
- Produces: manifest rows in `data/kitaru/cohort.jsonl` for arms `baseline-replay` and `swap-gpt4omini`

- [ ] **Step 1: Write the replay script**

Path A is used when api-notes says replay can target the `tick` role; otherwise Path B.

```python
"""Replay the cohort twice: unchanged (noise floor) and with the tick model swapped."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kitaru_record import MANIFEST, record_one  # noqa: E402

from pythia.logger import setup_logging  # noqa: E402

ARMS = {
    "baseline-replay": {},
    "swap-gpt4omini": {"tick": "openai:gpt-4o-mini"},
}


def recorded_rows() -> list[dict]:
    return [r for r in (json.loads(l) for l in MANIFEST.read_text().splitlines()) if r["arm"] == "recorded"]


async def path_b() -> None:
    """Fallback: re-run each recorded prompt/repeat under each arm, recorded as new sessions."""
    with MANIFEST.open("a") as fh:
        for arm, overrides in ARMS.items():
            for row in recorded_rows():
                out = await record_one(row["prompt"], row["repeat"], arm, overrides)
                out["replay_of"] = row["session_id"]
                fh.write(json.dumps(out) + "\n")
                fh.flush()
                print(f"{arm} replay_of={row['session_id']} coherence={out['coherence_rate']:.2f}")


def path_a(cmd_template: str) -> None:
    """Native: ask Kitaru to replay the cohort per arm. The command comes from api-notes."""
    for arm, overrides in ARMS.items():
        cmd = cmd_template.format(cohort="pythia-cohort-v1", arm=arm, tick=overrides.get("tick", ""))
        print("$", cmd)
        subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", choices=["A", "B"], required=True)
    ap.add_argument("--cmd", default="", help="Path A only: replay command template from api-notes, with {cohort} {arm} {tick}")
    args = ap.parse_args()
    setup_logging(level="INFO", log_dir="data/logs")
    if args.path == "A":
        if not args.cmd:
            ap.error("--cmd is required for path A")
        path_a(args.cmd)
    else:
        asyncio.run(path_b())
```

- [ ] **Step 2: Dry-check the arms against one row**

Run (Path B shown; for Path A pass `--path A --cmd "<template from api-notes>"`):

```bash
python3 -c "import json;rows=[json.loads(l) for l in open('data/kitaru/cohort.jsonl')];print(sum(r['arm']=='recorded' for r in rows))"
```

Expected: `10`.

- [ ] **Step 3: Run both arms**

```bash
python3 scripts/kitaru_replay.py --path B
```

Expected: 20 lines (10 per arm). In Path A, confirm in the dashboard that replay sessions show `requested_model=llama-3.1-8b-instant` and `model=gpt-4o-mini` on tick nodes for the swap arm, and unchanged models for the baseline arm. Under Path A, evaluations must still be written: run `record_one`'s evaluation step via the evaluator mechanism noted in api-notes, and log how evaluations attach to replay sessions.

- [ ] **Step 4: Log friction specific to replay**

Add rows covering at least: how faithful the unchanged replay was (did baseline direction match the recording?), whether overrides could target one role, any rate-limit behaviour during replay, and how long each arm took.

- [ ] **Step 5: Commit**

```bash
git add scripts/kitaru_replay.py docs/kitaru/friction-log.md
git commit -m "feat(kitaru): replay arms for noise floor and tick-model swap"
```

---

### Task 7: Results report

**Files:**
- Create: `src/pythia/experiment_report.py`
- Create: `scripts/kitaru_report.py`
- Test: `tests/test_experiment_report.py`
- Create (generated): `docs/kitaru/results.md`

**Interfaces:**
- Consumes: manifest rows (`arm`, `prompt`, `repeat`, `metrics`, `coherence_rate`, optional `replay_of`)
- Produces:
  - `summarize_arm(rows: list[dict]) -> dict[str, tuple[float, float]]` (metric → (mean, stdev)) for `coherence_rate`, `parse_failure_rate`, `target_validity_rate`, `stance_volatility`, `final_aggregate`
  - `direction_agreement(a: list[dict], b: list[dict]) -> float` (paired by `prompt` and `repeat`)
  - `render_markdown(rows: list[dict]) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from pythia.experiment_report import direction_agreement, render_markdown, summarize_arm


def _row(arm, prompt, repeat, coh, direction, agg=0.3):
    return {"arm": arm, "prompt": prompt, "repeat": repeat, "coherence_rate": coh,
            "metrics": {"parse_failure_rate": 0.0, "target_validity_rate": 1.0,
                        "stance_volatility": 0.05, "final_aggregate": agg, "direction": direction}}


def test_summarize_arm_mean_and_stdev():
    s = summarize_arm([_row("x", "p", 0, 0.6, "sell"), _row("x", "p", 1, 1.0, "sell")])
    mean, sd = s["coherence_rate"]
    assert abs(mean - 0.8) < 1e-9 and abs(sd - 0.2828427) < 1e-6


def test_direction_agreement_pairs_by_prompt_and_repeat():
    a = [_row("a", "p", 0, 1, "sell"), _row("a", "q", 0, 1, "buy")]
    b = [_row("b", "q", 0, 1, "buy"), _row("b", "p", 0, 1, "neutral")]
    assert direction_agreement(a, b) == 0.5


def test_render_markdown_has_all_arms():
    rows = [_row(arm, "p", 0, 0.8, "sell") for arm in ("recorded", "baseline-replay", "swap-gpt4omini")]
    md = render_markdown(rows)
    for arm in ("recorded", "baseline-replay", "swap-gpt4omini"):
        assert arm in md
    assert "Direction agreement" in md
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_experiment_report.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Aggregate experiment manifest rows into per-arm statistics and a markdown report."""

from __future__ import annotations

from statistics import mean, stdev

METRICS = ["coherence_rate", "parse_failure_rate", "target_validity_rate", "stance_volatility", "final_aggregate"]
ARM_ORDER = ["recorded", "baseline-replay", "swap-gpt4omini"]


def _value(row: dict, metric: str) -> float:
    return float(row["coherence_rate"] if metric == "coherence_rate" else row["metrics"][metric])


def summarize_arm(rows: list[dict]) -> dict[str, tuple[float, float]]:
    out = {}
    for m in METRICS:
        vals = [_value(r, m) for r in rows]
        out[m] = (mean(vals), stdev(vals) if len(vals) > 1 else 0.0)
    return out


def direction_agreement(a: list[dict], b: list[dict]) -> float:
    index = {(r["prompt"], r["repeat"]): r["metrics"]["direction"] for r in b}
    pairs = [(r["metrics"]["direction"], index[(r["prompt"], r["repeat"])]) for r in a if (r["prompt"], r["repeat"]) in index]
    if not pairs:
        return 0.0
    return sum(1 for x, y in pairs if x == y) / len(pairs)


def render_markdown(rows: list[dict]) -> str:
    by_arm = {arm: [r for r in rows if r["arm"] == arm] for arm in ARM_ORDER}
    lines = ["# Kitaru experiment results", "", "| Metric | " + " | ".join(ARM_ORDER) + " |", "|---|" + "---|" * len(ARM_ORDER)]
    stats = {arm: summarize_arm(rs) for arm, rs in by_arm.items() if rs}
    for m in METRICS:
        cells = [f"{stats[a][m][0]:.3f} ± {stats[a][m][1]:.3f}" if a in stats else "n/a" for a in ARM_ORDER]
        lines.append(f"| {m} | " + " | ".join(cells) + " |")
    lines += ["", "## Direction agreement with the recording", ""]
    rec = by_arm["recorded"]
    for arm in ARM_ORDER[1:]:
        if by_arm[arm] and rec:
            lines.append(f"- {arm}: {direction_agreement(rec, by_arm[arm]):.0%}")
    lines += ["", f"Sessions per arm: " + ", ".join(f"{a}={len(by_arm[a])}" for a in ARM_ORDER)]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_experiment_report.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write the report script and generate results**

```python
"""Render docs/kitaru/results.md from the experiment manifest."""

import json
from pathlib import Path

from pythia.experiment_report import render_markdown

rows = [json.loads(l) for l in Path("data/kitaru/cohort.jsonl").read_text().splitlines() if l.strip()]
Path("docs/kitaru/results.md").write_text(render_markdown(rows))
print(Path("docs/kitaru/results.md").read_text())
```

Save as `scripts/kitaru_report.py`, then run:

```bash
python3 scripts/kitaru_report.py
```

Expected: a table with three columns of numbers and two agreement percentages. Interpretation rule for the memo: the swap arm "differs" on a metric only if its mean is outside the baseline-replay mean ± 2 standard deviations.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/experiment_report.py scripts/kitaru_report.py tests/test_experiment_report.py docs/kitaru/results.md
git commit -m "feat(kitaru): experiment results report"
```

---

### Task 8: Feedback memo and cover message

**Files:**
- Create: `docs/kitaru/memo.md`
- Create: `docs/kitaru/cover-message.md`

- [ ] **Step 1: Write the memo from evidence**

`docs/kitaru/memo.md` must have these sections, each backed by the friction log or results:

```markdown
# Kitaru feedback from building on Pythia

## What we built
Pythia (multi-agent opinion simulation, custom httpx LLM clients, no framework, no tools). Wrapper at the LLM-client boundary; 10 recorded sessions; noise-floor replay; tick-model swap to gpt-4o-mini; 5 deterministic evaluators plus an LLM judge.

## Results
<paste the results table; one paragraph interpreting it against the ±2σ rule>

## What worked
<3-5 bullets, each tied to a concrete moment>

## Friction, ranked
| # | Severity | Issue | Evidence (friction-log row) | Suggested fix |
<sorted: blockers, then major, then minor>

## Product observations
- Positioning: launch posts describe durable execution; current docs describe replay-based evaluation.
- Custom adapters for non-framework agents: docs defer to an agent skill rather than a code example.
- Replay semantics for tool-less, stochastic agents: what an "unchanged replay" means when there are no tool calls to pin.
- Self-hosted path not evaluated (managed cloud used).

## Would we keep using it?
<honest yes / no / conditional, with the condition>
```

- [ ] **Step 2: Write the cover message**

`docs/kitaru/cover-message.md`: at most 150 words, with the top 3 findings (one positive, two friction items) and a link placeholder `[memo link]` for the shared doc.

- [ ] **Step 3: Review with the user before sending**

Show both files to the user. Publishing the memo as a shareable doc and sending the message are outward-facing: do neither without the user's explicit go-ahead.

- [ ] **Step 4: Commit**

```bash
git add docs/kitaru/memo.md docs/kitaru/cover-message.md
git commit -m "docs(kitaru): feedback memo and cover message"
```
