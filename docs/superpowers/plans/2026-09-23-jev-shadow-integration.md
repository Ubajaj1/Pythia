# Jev (TypeSafe) Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put Jev behind four judgment-shaped pieces of Pythia (behaviour settings, coherence checking, expressed-stance scoring, prompt screening), each switchable `off | shadow | primary`, with shadow comparisons saved on every run and a report that decides when a piece may move to primary.

**Architecture:** A `pythia.jev` package owns everything Jev. `core.py` defines our own question/answer types, the mode switch, a `JevAsker` protocol, the SDK adapter (the only file importing `typesafe_sdk`), and a shadow-record collector that uses a `ContextVar` like `pythia.usage`. Pure conversions live in `mapping.py`. One module per piece (`behaviour.py`, `coherence.py`, `stance.py`, `screening.py`) exposes one async function that existing code calls at a single hook point. Every Jev failure falls back to the current LLM path.

**Tech Stack:** Python 3.11, `typesafe-sdk` (`AsyncTypeSafeClient`, `Noul`, `NoulCriteria`, `Choice`, `Score`), model `jev-latest`, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-09-23-jev-integration-design.md`

## Global Constraints

- Branch `feat/jev-shadow` from `origin/main` **after** the backend-refresh branch has merged (this plan uses `pythia.usage.record_usage`, `RunResultWithInsights.quality`, and `Agent.archetype` from it).
- `typesafe-sdk` is an optional extra `jev`; `from typesafe_sdk import ...` appears only in `src/pythia/jev/core.py`, inside `SdkJev`.
- Auth: `TYPESAFE_API_KEY` from the environment. No key means every piece is `off`, whatever its mode variable says.
- Modes: `PYTHIA_JEV_BEHAVIOUR`, `PYTHIA_JEV_COHERENCE`, `PYTHIA_JEV_STANCE`, `PYTHIA_JEV_SCREENING` ∈ {`off`, `shadow`, `primary`}; default `off`. Stance scoring treats `primary` as `shadow`.
- Confidence threshold `PYTHIA_JEV_THRESHOLD`, default `0.5`. Promotion analysis uses 0.7.
- Noul answers have no confidence field; derive it as `abs(2p - 1)`.
- Score answers are continuous positions in `[0, levels - 1]`; stance = `(score + 0.5) / levels`.
- Jev never produces text: personas, behavioural rules, tick messages, and incoherence summaries stay with the LLM.
- Any exception from Jev is logged and the LLM path is used; a simulation must never fail because of Jev.

---

### Task 1: Core — types, modes, SDK adapter, shadow collector

**Files:**
- Create: `src/pythia/jev/__init__.py` (empty)
- Create: `src/pythia/jev/core.py`
- Modify: `pyproject.toml` (extra `jev = ["typesafe-sdk"]`)
- Test: `tests/test_jev_core.py`

**Interfaces:**
- Produces:
  - `NoulQ(instructions: str, true: str | None = None, false: str | None = None)`, `ChoiceQ(instructions: str, options: dict[str, str])`, `ScoreQ(instructions: str, levels: list[str])`; `Question = NoulQ | ChoiceQ | ScoreQ`
  - `Answer(value: float | str, confidence: float, probabilities: dict[str, float])`
  - `class JevAsker(Protocol): async def ask(self, state: dict | str, questions: dict[str, Question]) -> dict[str, Answer]`
  - `jev_mode(piece: str) -> Literal["off", "shadow", "primary"]`; `threshold() -> float`; `get_jev() -> JevAsker | None`
  - `start_shadow() -> tuple[list[dict], Token]`, `stop_shadow(token) -> None`, `record_shadow(piece: str, key: str, llm, jev, confidence: float, agree: bool, used: str) -> None`
  - `class SdkJev` implementing `JevAsker`

- [ ] **Step 1: Branch and dependency**

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
git checkout -b feat/jev-shadow
```

Add to `[project.optional-dependencies]` in `pyproject.toml`:

```toml
jev = [
    "typesafe-sdk",
]
```

Run: `pip install -e ".[dev,jev]"`

- [ ] **Step 2: Write the failing tests**

```python
"""Tests for Jev core: modes, shadow collection, SDK answer conversion."""

import asyncio
from types import SimpleNamespace

from pythia.jev import core
from pythia.jev.core import Answer, ChoiceQ, NoulQ, ScoreQ, jev_mode, record_shadow, start_shadow, stop_shadow


def test_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("PYTHIA_JEV_BEHAVIOUR", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    assert jev_mode("behaviour") == "off"


def test_mode_reads_env(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setenv("PYTHIA_JEV_COHERENCE", "shadow")
    assert jev_mode("coherence") == "shadow"


def test_mode_off_without_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("PYTHIA_JEV_COHERENCE", "primary")
    assert jev_mode("coherence") == "off"


def test_invalid_mode_is_off(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setenv("PYTHIA_JEV_STANCE", "yes")
    assert jev_mode("stance") == "off"


async def test_shadow_collects_across_tasks():
    records, token = start_shadow()
    try:
        async def rec(i):
            record_shadow("coherence", f"a{i}", True, True, 0.9, True, "llm")
        await asyncio.gather(rec(1), rec(2))
    finally:
        stop_shadow(token)
    assert {r["key"] for r in records} == {"a1", "a2"}
    assert records[0]["piece"] == "coherence"


def test_record_without_scope_is_noop():
    record_shadow("coherence", "x", 1, 1, 1.0, True, "llm")


def test_convert_response():
    resp = SimpleNamespace(
        nouls={"n": SimpleNamespace(noul=0.9)},
        choices={"c": SimpleNamespace(choice="b", confidence=0.8, probabilities={"a": 0.1, "b": 0.9})},
        scores={"s": SimpleNamespace(score=1.5, confidence=0.6, probabilities={"0": 0.1, "1": 0.4, "2": 0.5})},
    )
    qs = {"n": NoulQ("?"), "c": ChoiceQ("?", {"a": "A", "b": "B"}), "s": ScoreQ("?", ["x", "y", "z"])}
    out = core._convert(resp, qs)
    assert out["n"].value == 0.9 and abs(out["n"].confidence - 0.8) < 1e-9
    assert out["c"].value == "b" and out["c"].confidence == 0.8
    assert out["s"].value == 1.5 and out["s"].probabilities == {"0": 0.1, "1": 0.4, "2": 0.5}
```

- [ ] **Step 3: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.jev'`.

- [ ] **Step 4: Implement `src/pythia/jev/core.py`**

```python
"""Jev core: question/answer types, per-piece modes, SDK adapter, shadow records."""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Literal, Protocol, Union

logger = logging.getLogger(__name__)

Mode = Literal["off", "shadow", "primary"]
_MODES = {"off", "shadow", "primary"}
JEV_MODEL = "jev-latest"


@dataclass(frozen=True)
class NoulQ:
    instructions: str
    true: str | None = None
    false: str | None = None


@dataclass(frozen=True)
class ChoiceQ:
    instructions: str
    options: dict[str, str]


@dataclass(frozen=True)
class ScoreQ:
    instructions: str
    levels: list[str]


Question = Union[NoulQ, ChoiceQ, ScoreQ]


@dataclass(frozen=True)
class Answer:
    value: float | str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)


class JevAsker(Protocol):
    async def ask(self, state: dict | str, questions: dict[str, Question]) -> dict[str, Answer]: ...


def jev_mode(piece: str) -> Mode:
    if not os.getenv("TYPESAFE_API_KEY"):
        return "off"
    raw = os.getenv(f"PYTHIA_JEV_{piece.upper()}", "off").strip().lower()
    if raw not in _MODES:
        logger.warning("Ignoring invalid PYTHIA_JEV_%s=%r (expected off|shadow|primary)", piece.upper(), raw)
        return "off"
    return raw  # type: ignore[return-value]


def threshold() -> float:
    return float(os.getenv("PYTHIA_JEV_THRESHOLD", "0.5"))


# ── shadow records ───────────────────────────────────────────────────────────
_shadow: ContextVar[list[dict] | None] = ContextVar("pythia_jev_shadow", default=None)


def start_shadow() -> tuple[list[dict], Token]:
    records: list[dict] = []
    return records, _shadow.set(records)


def stop_shadow(token: Token) -> None:
    try:
        _shadow.reset(token)
    except ValueError:
        _shadow.set(None)


def record_shadow(piece: str, key: str, llm, jev, confidence: float, agree: bool, used: str) -> None:
    records = _shadow.get()
    if records is None:
        return
    records.append({"piece": piece, "key": key, "llm": llm, "jev": jev,
                    "confidence": round(float(confidence), 4), "agree": bool(agree), "used": used})


# ── SDK adapter ──────────────────────────────────────────────────────────────
def _convert(response, questions: dict[str, Question]) -> dict[str, Answer]:
    out: dict[str, Answer] = {}
    for key, q in questions.items():
        if isinstance(q, NoulQ):
            p = float(response.nouls[key].noul)
            out[key] = Answer(p, abs(2 * p - 1), {"true": p, "false": 1 - p})
        elif isinstance(q, ChoiceQ):
            a = response.choices[key]
            out[key] = Answer(a.choice, float(a.confidence), {str(k): float(v) for k, v in dict(a.probabilities).items()})
        else:
            a = response.scores[key]
            out[key] = Answer(float(a.score), float(a.confidence), {str(k): float(v) for k, v in dict(a.probabilities).items()})
    return out


class SdkJev:
    """JevAsker backed by typesafe-sdk. The only place that imports it."""

    async def ask(self, state: dict | str, questions: dict[str, Question]) -> dict[str, Answer]:
        from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, NoulCriteria, Score

        sdk_qs = {}
        for key, q in questions.items():
            if isinstance(q, NoulQ):
                criteria = NoulCriteria(true=q.true, false=q.false) if (q.true or q.false) else None
                sdk_qs[key] = Noul(instructions=q.instructions, criteria=criteria) if criteria else Noul(instructions=q.instructions)
            elif isinstance(q, ChoiceQ):
                sdk_qs[key] = Choice(instructions=q.instructions, criteria=q.options)
            else:
                sdk_qs[key] = Score(instructions=q.instructions, criteria=q.levels)

        async with AsyncTypeSafeClient() as client:
            response = await client.system_one(model=JEV_MODEL, state=state, questions=sdk_qs)

        usage = getattr(response, "usage", None)
        if usage is not None:
            from pythia.usage import record_usage
            record_usage(JEV_MODEL, int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0))
        return _convert(response, questions)


_client: JevAsker | None = None


def get_jev() -> JevAsker | None:
    global _client
    if not os.getenv("TYPESAFE_API_KEY"):
        return None
    if _client is None:
        _client = SdkJev()
    return _client
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_jev_core.py -v`
Expected: 7 passed.

- [ ] **Step 6: Live smoke test of the adapter (uses the real key; a fraction of a cent)**

```bash
python3 -c "
import asyncio
from pythia.jev.core import SdkJev, NoulQ, ChoiceQ, ScoreQ
async def main():
    out = await SdkJev().ask({'document':'I was charged twice. Fix this now.'},
        {'billing': NoulQ('Is this about billing?'),
         'tone': ChoiceQ('Tone?', {'calm':'calm','angry':'angry'}),
         'urgency': ScoreQ('How urgent?', ['can wait','this week','today'])})
    print(out)
asyncio.run(main())"
```

Expected: three `Answer`s; `billing` value near 1, `urgency` near 2. If an attribute name differs (for example `response.answers` instead of `response.nouls`), fix `_convert` and its test to match the real response.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/pythia/jev/__init__.py src/pythia/jev/core.py tests/test_jev_core.py
git commit -m "feat(jev): core types, modes, SDK adapter, shadow records"
```

---

### Task 2: Pure mappings

**Files:**
- Create: `src/pythia/jev/mapping.py`
- Test: `tests/test_jev_mapping.py`

**Interfaces:**
- Produces:
  - `STRENGTH_LEVELS: list[str]` (4 descriptions), `STRENGTH_VALUES = [0.3, 0.5, 0.7, 0.85]`
  - `strength_from_score(score: float) -> float`
  - `stance_from_score(score: float, n_levels: int) -> float`
  - `clamp(v: float, lo: float, hi: float) -> float`
  - `stance_bin(v: float, n_levels: int = 5) -> int`; `ordinal_agree(a: float, b: float, n_levels: int = 5) -> bool`
  - `RELATION_OPTIONS: dict[str, str]` with keys `none, follows, respects, distrusts, rivals`
  - `prune_relationships(pairs: dict[tuple[str, str], Answer], k_max: int = 3) -> dict[str, list[tuple[str, str, float]]]` → source id → [(target, type, weight)]

- [ ] **Step 1: Write the failing tests**

```python
from pythia.jev.core import Answer
from pythia.jev.mapping import (
    clamp, ordinal_agree, prune_relationships, stance_bin, stance_from_score, strength_from_score,
)


def test_strength_interpolates_between_levels():
    assert strength_from_score(0) == 0.3
    assert strength_from_score(3) == 0.85
    assert abs(strength_from_score(1.5) - 0.6) < 1e-9


def test_stance_from_score_uses_bin_midpoints():
    assert abs(stance_from_score(0, 5) - 0.1) < 1e-9
    assert abs(stance_from_score(4, 5) - 0.9) < 1e-9
    assert abs(stance_from_score(2.5, 5) - 0.6) < 1e-9


def test_clamp():
    assert clamp(0.9, 0.2, 0.4) == 0.4 and clamp(0.1, 0.2, 0.4) == 0.2


def test_ordinal_agree_allows_adjacent_bins():
    assert stance_bin(0.99) == 4
    assert ordinal_agree(0.25, 0.45)
    assert not ordinal_agree(0.1, 0.5)


def test_prune_relationships_keeps_top_three_non_none():
    pairs = {
        ("a", "b"): Answer("follows", 0.9, {"follows": 0.9}),
        ("a", "c"): Answer("distrusts", 0.7, {"distrusts": 0.7}),
        ("a", "d"): Answer("none", 0.9, {"none": 0.9}),
        ("a", "e"): Answer("respects", 0.6, {"respects": 0.6}),
        ("a", "f"): Answer("rivals", 0.5, {"rivals": 0.5}),
    }
    out = prune_relationships(pairs)
    assert [t for t, _, _ in out["a"]] == ["b", "c", "e"]
    assert out["a"][0] == ("b", "follows", 0.9)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_mapping.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Pure conversions between Jev answers and Pythia values."""

from __future__ import annotations

from pythia.jev.core import Answer

STRENGTH_LEVELS = [
    "Mild: notices the bias and can set it aside when shown evidence",
    "Moderate: the bias shapes first reactions but can be argued down",
    "Strong: the bias usually wins over contrary evidence",
    "Rigid: the bias defines how this person sees every new fact",
]
STRENGTH_VALUES = [0.3, 0.5, 0.7, 0.85]

RELATION_OPTIONS = {
    "none": "No meaningful relationship",
    "follows": "Takes cues from and tends to copy the other",
    "respects": "Values the other's judgment without copying it",
    "distrusts": "Discounts what the other says",
    "rivals": "Competes with the other and tends to take the opposite side",
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def strength_from_score(score: float) -> float:
    s = clamp(score, 0, len(STRENGTH_VALUES) - 1)
    i = min(int(s), len(STRENGTH_VALUES) - 2)
    f = s - i
    return STRENGTH_VALUES[i] + (STRENGTH_VALUES[i + 1] - STRENGTH_VALUES[i]) * f


def stance_from_score(score: float, n_levels: int) -> float:
    return clamp((score + 0.5) / n_levels, 0.0, 1.0)


def stance_bin(v: float, n_levels: int = 5) -> int:
    return min(int(v * n_levels), n_levels - 1)


def ordinal_agree(a: float, b: float, n_levels: int = 5) -> bool:
    return abs(stance_bin(a, n_levels) - stance_bin(b, n_levels)) <= 1


def prune_relationships(pairs: dict[tuple[str, str], Answer], k_max: int = 3) -> dict[str, list[tuple[str, str, float]]]:
    by_source: dict[str, list[tuple[str, str, float]]] = {}
    for (src, tgt), ans in pairs.items():
        if ans.value == "none":
            continue
        weight = ans.probabilities.get(str(ans.value), ans.confidence)
        by_source.setdefault(src, []).append((tgt, str(ans.value), round(float(weight), 4)))
    return {src: sorted(rels, key=lambda r: -r[2])[:k_max] for src, rels in by_source.items()}
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_jev_mapping.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/jev/mapping.py tests/test_jev_mapping.py
git commit -m "feat(jev): pure mappings for strength, stance, relationships"
```

---

### Task 3: Shadow records on runs

**Files:**
- Modify: `src/pythia/models.py` (`RunResultWithInsights.jev_shadow`, `OracleLoopResult.jev_shadow`)
- Modify: `src/pythia/orchestrator.py` (`stream_simulation`, `run_simulation`)
- Modify: `src/pythia/oracle_loop.py` (`run_oracle_loop`, `stream_oracle_loop`)
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `start_shadow/stop_shadow` (Task 1)
- Produces: `RunResultWithInsights.jev_shadow: list[dict] = []`, `OracleLoopResult.jev_shadow: list[dict] = []`

- [ ] **Step 1: Write the failing test** (append to `tests/test_orchestrator.py`)

```python
async def test_done_payload_carries_jev_shadow(tmp_path):
    llm = FakeLLMClient(responses=make_all_responses())
    events = [e async for e in stream_simulation("q", llm=llm, runs_dir=str(tmp_path))]
    assert events[-1]["data"]["jev_shadow"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_orchestrator.py -v -k jev_shadow`
Expected: FAIL with `KeyError: 'jev_shadow'`.

- [ ] **Step 3: Implement**

`models.py`: add `jev_shadow: list[dict] = Field(default_factory=list)` as the last field of `RunResultWithInsights` and of `OracleLoopResult`.

`orchestrator.py`: import `from pythia.jev.core import start_shadow, stop_shadow`. In both `stream_simulation` and `run_simulation`, next to the usage scope added by the backend plan, open `shadow, shadow_token = start_shadow()` and close it in the same `finally` with `stop_shadow(shadow_token)`; pass `jev_shadow=shadow` to `RunResultWithInsights(...)`.

`oracle_loop.py`: do the same in `run_oracle_loop` (open at the top of the body, pass `jev_shadow=shadow` to the `OracleLoopResult(...)` at line ~150) and in `stream_oracle_loop` (open at the top, pass to the `OracleLoopResult(...)` at line ~369 before the `done` yield).

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/models.py src/pythia/orchestrator.py src/pythia/oracle_loop.py tests/test_orchestrator.py
git commit -m "feat(jev): attach shadow records to run and oracle results"
```

---

### Task 4: Behaviour settings

**Files:**
- Create: `src/pythia/jev/behaviour.py`
- Modify: `src/pythia/generator.py` (`generate_agents`, just before the final log)
- Test: `tests/test_jev_behaviour.py`

**Interfaces:**
- Consumes: `BIAS_CATALOG` (`canonical_id`, `name`, `layman`), `Agent`, `Relationship`, `ScenarioBlueprint`, mapping helpers, `record_shadow`, `threshold`, `get_jev`, `jev_mode`
- Produces: `async def apply_behaviour_judgement(agents: list[Agent], blueprint: ScenarioBlueprint, jev: JevAsker | None = None, mode: str | None = None) -> list[Agent]`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for Jev behaviour settings (fake Jev)."""

from pythia.jev.behaviour import apply_behaviour_judgement
from pythia.jev.core import Answer, start_shadow, stop_shadow
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint


def _bp():
    return ScenarioBlueprint(
        scenario_type="t", title="T", description="d", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        agent_archetypes=[AgentArchetype(role="trader", count=2, description="d", bias="anchoring", stance_range=(0.2, 0.6))],
        dynamics="x", tick_count=3,
    )


def _agents():
    return [
        Agent(id="a", name="A", role="trader", persona="p", bias="anchoring", bias_strength=0.5,
              initial_stance=0.3, behavioral_rules=["r"], archetype="trader",
              relationships=[Relationship(target="b", type="follows", weight=0.5)]),
        Agent(id="b", name="B", role="trader", persona="p", bias="anchoring", bias_strength=0.5,
              initial_stance=0.5, behavioral_rules=["r"], archetype="trader"),
    ]


class FakeJev:
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def ask(self, state, questions):
        self.calls.append(questions)
        return {k: self.answers[k] for k in questions}


def _answers(conf=0.9):
    return {
        "a:bias": Answer("loss_aversion", conf, {"loss_aversion": conf}),
        "a:strength": Answer(3.0, conf, {}),
        "a:stance": Answer(0.0, conf, {}),
        "b:bias": Answer("anchoring", conf, {"anchoring": conf}),
        "b:strength": Answer(1.0, conf, {}),
        "b:stance": Answer(2.0, conf, {}),
        "rel:a->b": Answer("distrusts", conf, {"distrusts": conf}),
        "rel:b->a": Answer("none", conf, {"none": conf}),
    }


async def test_off_returns_agents_untouched():
    agents = _agents()
    out = await apply_behaviour_judgement(agents, _bp(), jev=FakeJev(_answers()), mode="off")
    assert out == agents


async def test_shadow_records_but_keeps_llm_values():
    records, token = start_shadow()
    try:
        out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers()), mode="shadow")
    finally:
        stop_shadow(token)
    assert out[0].bias == "anchoring" and out[0].initial_stance == 0.3
    bias_a = next(r for r in records if r["key"] == "a:bias")
    assert bias_a["llm"] == "anchoring" and bias_a["jev"] == "loss_aversion" and bias_a["agree"] is False
    assert all(r["used"] == "llm" for r in records)


async def test_primary_applies_confident_answers_and_clamps_stance():
    out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers()), mode="primary")
    a = out[0]
    assert a.bias == "loss_aversion"
    assert a.bias_strength == 0.85
    assert a.initial_stance == 0.2  # 0.1 clamped to archetype range (0.2, 0.6)
    assert [(r.target, r.type) for r in a.relationships] == [("b", "distrusts")]
    assert out[1].relationships == []


async def test_primary_keeps_llm_when_unsure():
    out = await apply_behaviour_judgement(_agents(), _bp(), jev=FakeJev(_answers(conf=0.2)), mode="primary")
    assert out[0].bias == "anchoring" and out[0].initial_stance == 0.3


async def test_jev_error_falls_back():
    class Boom:
        async def ask(self, state, questions):
            raise RuntimeError("down")
    agents = _agents()
    assert await apply_behaviour_judgement(agents, _bp(), jev=Boom(), mode="primary") == agents
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_behaviour.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pythia/jev/behaviour.py`**

```python
"""Jev behaviour settings: bias, bias strength, initial stance, relationships."""

from __future__ import annotations

import logging

from pythia.biases import BIAS_CATALOG
from pythia.jev.core import ChoiceQ, JevAsker, ScoreQ, get_jev, jev_mode, record_shadow, threshold
from pythia.jev.mapping import (
    RELATION_OPTIONS, STRENGTH_LEVELS, clamp, ordinal_agree, prune_relationships,
    stance_from_score, strength_from_score,
)
from pythia.models import Agent, Relationship, ScenarioBlueprint

logger = logging.getLogger(__name__)
PIECE = "behaviour"


def _state(agents: list[Agent], blueprint: ScenarioBlueprint) -> dict:
    return {
        "scenario": f"{blueprint.title}. {blueprint.description}",
        "stance_spectrum_low_to_high": blueprint.stance_spectrum,
        "cast": [{"id": a.id, "name": a.name, "role": a.role, "persona": a.persona} for a in agents],
    }


def _agent_questions(agents: list[Agent], blueprint: ScenarioBlueprint) -> dict:
    bias_options = {cid: f"{e.name}: {e.layman}" for cid, e in BIAS_CATALOG.items()}
    qs = {}
    for a in agents:
        who = f"{a.name} (id {a.id})"
        qs[f"{a.id}:bias"] = ChoiceQ(f"Which cognitive bias best fits {who}'s persona?", bias_options)
        qs[f"{a.id}:strength"] = ScoreQ(f"How strongly does that bias shape {who}'s thinking?", STRENGTH_LEVELS)
        qs[f"{a.id}:stance"] = ScoreQ(f"Before any discussion, where does {who} stand on the scenario?", blueprint.stance_spectrum)
    return qs


def _relation_questions(agents: list[Agent]) -> dict:
    return {
        f"rel:{a.id}->{b.id}": ChoiceQ(f"How does {a.name} relate to {b.name}?", RELATION_OPTIONS)
        for a in agents for b in agents if a.id != b.id
    }


def _range_for(agent: Agent, blueprint: ScenarioBlueprint) -> tuple[float, float]:
    for arch in blueprint.agent_archetypes:
        if arch.role == (agent.archetype or agent.role):
            return arch.stance_range
    return (0.0, 1.0)


async def apply_behaviour_judgement(
    agents: list[Agent], blueprint: ScenarioBlueprint,
    jev: JevAsker | None = None, mode: str | None = None,
) -> list[Agent]:
    mode = mode or jev_mode(PIECE)
    jev = jev or get_jev()
    if mode == "off" or jev is None:
        return agents
    try:
        state = _state(agents, blueprint)
        answers = await jev.ask(state, _agent_questions(agents, blueprint))
        answers |= await jev.ask(state, _relation_questions(agents))
    except Exception:
        logger.exception("Jev behaviour judgement failed; keeping LLM values")
        return agents

    primary, cut, n = mode == "primary", threshold(), len(blueprint.stance_spectrum)
    rel_pairs = {tuple(k[4:].split("->")): v for k, v in answers.items() if k.startswith("rel:")}
    jev_rels = prune_relationships(rel_pairs)
    out = []
    for a in agents:
        upd: dict = {}
        bias = answers[f"{a.id}:bias"]
        use = primary and bias.confidence >= cut
        record_shadow(PIECE, f"{a.id}:bias", a.bias, bias.value, bias.confidence, bias.value == a.bias, "jev" if use else "llm")
        if use:
            upd["bias"] = str(bias.value)

        strength = answers[f"{a.id}:strength"]
        s_val = round(strength_from_score(float(strength.value)), 4)
        use = primary and strength.confidence >= cut
        record_shadow(PIECE, f"{a.id}:strength", a.bias_strength, s_val, strength.confidence, abs(s_val - a.bias_strength) <= 0.2, "jev" if use else "llm")
        if use:
            upd["bias_strength"] = s_val

        stance = answers[f"{a.id}:stance"]
        lo, hi = _range_for(a, blueprint)
        st_val = round(clamp(stance_from_score(float(stance.value), n), lo, hi), 4)
        use = primary and stance.confidence >= cut
        record_shadow(PIECE, f"{a.id}:stance", a.initial_stance, st_val, stance.confidence, ordinal_agree(st_val, a.initial_stance, n), "jev" if use else "llm")
        if use:
            upd["initial_stance"] = st_val

        llm_rel = {r.target: r.type for r in a.relationships}
        mine = jev_rels.get(a.id, [])
        confident = [r for r in mine if r[2] >= cut]
        record_shadow(PIECE, f"{a.id}:relationships", llm_rel, {t: ty for t, ty, _ in mine},
                      min((r[2] for r in mine), default=1.0), llm_rel == {t: ty for t, ty, _ in mine},
                      "jev" if primary else "llm")
        if primary:
            upd["relationships"] = [Relationship(target=t, type=ty, weight=w) for t, ty, w in confident]
        out.append(a.model_copy(update=upd) if upd else a)
    return out
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_jev_behaviour.py -v`
Expected: 5 passed.

- [ ] **Step 5: Hook into the generator**

In `src/pythia/generator.py`, add `from pythia.jev.behaviour import apply_behaviour_judgement` and, in `generate_agents` immediately before the final `logger.info("Generation complete ...")`, add:

```python
    agents = await apply_behaviour_judgement(agents, blueprint)
```

Run: `python3 -m pytest -q`
Expected: all pass (with no `TYPESAFE_API_KEY` in the test environment, the hook is a no-op).

- [ ] **Step 6: Commit**

```bash
git add src/pythia/jev/behaviour.py src/pythia/generator.py tests/test_jev_behaviour.py
git commit -m "feat(jev): behaviour settings judge in shadow/primary"
```

---

### Task 5: Coherence checker

**Files:**
- Create: `src/pythia/jev/coherence.py`
- Modify: `src/pythia/evaluator.py` (`evaluate_agent`)
- Test: `tests/test_jev_coherence.py`

**Interfaces:**
- Consumes: `EVAL_PROMPT`'s judging rules (copied into the Noul instructions), `_format_history` from `evaluator.py`
- Produces: `async def judge_coherence(agent: Agent, history: str, jev: JevAsker) -> Answer`; `evaluate_agent(agent, tick_pairs, llm, jev: JevAsker | None = None, mode: str | None = None)`
- Constant: `JEV_INCOHERENT_FALLBACK_SUMMARY = "Stated reasoning did not match actions (flagged by Jev)."`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for Jev-assisted coherence evaluation."""

from pythia.evaluator import evaluate_agent
from pythia.jev.coherence import JEV_INCOHERENT_FALLBACK_SUMMARY
from pythia.jev.core import Answer, start_shadow, stop_shadow
from tests.conftest import FakeLLMClient
from tests.test_evaluator import make_agent, make_tick_pairs


class FakeJev:
    def __init__(self, p):
        self.p = p

    async def ask(self, state, questions):
        return {k: Answer(self.p, abs(2 * self.p - 1), {}) for k in questions}


async def test_shadow_uses_llm_and_records():
    llm = FakeLLMClient(responses=[{"is_coherent": False, "incoherence_summary": "x"}])
    records, token = start_shadow()
    try:
        ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.95), mode="shadow")
    finally:
        stop_shadow(token)
    assert ev.is_coherent is False and len(llm.calls) == 1
    assert records[0]["piece"] == "coherence" and records[0]["agree"] is False


async def test_primary_confident_coherent_skips_llm():
    llm = FakeLLMClient(responses=[])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.95), mode="primary")
    assert ev.is_coherent is True and llm.calls == []


async def test_primary_confident_incoherent_asks_llm_for_summary():
    llm = FakeLLMClient(responses=[{"is_coherent": False, "incoherence_summary": "Sold while praising the asset."}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.05), mode="primary")
    assert ev.is_coherent is False and ev.incoherence_summary == "Sold while praising the asset."


async def test_primary_incoherent_but_llm_disagrees_uses_fallback_summary():
    llm = FakeLLMClient(responses=[{"is_coherent": True, "incoherence_summary": None}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.05), mode="primary")
    assert ev.is_coherent is False and ev.incoherence_summary == JEV_INCOHERENT_FALLBACK_SUMMARY


async def test_primary_unsure_defers_to_llm():
    llm = FakeLLMClient(responses=[{"is_coherent": True, "incoherence_summary": None}])
    ev = await evaluate_agent(make_agent(), make_tick_pairs(), llm, jev=FakeJev(0.55), mode="primary")
    assert ev.is_coherent is True and len(llm.calls) == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_coherence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.jev.coherence'`.

- [ ] **Step 3: Implement `src/pythia/jev/coherence.py`**

```python
"""Jev coherence judge: is an agent's stated reasoning consistent with its actions?"""

from __future__ import annotations

from pythia.jev.core import Answer, JevAsker, NoulQ
from pythia.models import Agent

PIECE = "coherence"
JEV_INCOHERENT_FALLBACK_SUMMARY = "Stated reasoning did not match actions (flagged by Jev)."

_INSTRUCTIONS = (
    "Is this agent's reasoning coherent across the history? Changing its mind or deviating from "
    "its archetype is fine. It is incoherent only if stated reasoning directly contradicts the action "
    "taken, reasoning contradicts itself within one tick, or a stance shift larger than 0.3 has empty "
    "or generic reasoning."
)


async def judge_coherence(agent: Agent, history: str, jev: JevAsker) -> Answer:
    state = {
        "agent": f"{agent.name} ({agent.role}), bias: {agent.bias}",
        "behavioral_rules": agent.behavioral_rules,
        "history": history,
    }
    q = NoulQ(_INSTRUCTIONS, true="Reasoning is consistent with actions", false="Reasoning contradicts actions or big shifts are unexplained")
    return (await jev.ask(state, {"coherent": q}))["coherent"]
```

- [ ] **Step 4: Integrate into `evaluate_agent`**

In `src/pythia/evaluator.py`:

```python
from pythia.jev.coherence import JEV_INCOHERENT_FALLBACK_SUMMARY, PIECE as COHERENCE_PIECE, judge_coherence
from pythia.jev.core import JevAsker, get_jev, jev_mode, record_shadow, threshold
```

Change the signature to `async def evaluate_agent(agent, tick_pairs, llm, jev: JevAsker | None = None, mode: str | None = None) -> AgentEvaluation:` and restructure the body:

```python
    mode = mode or jev_mode(COHERENCE_PIECE)
    jev = jev or get_jev()
    history = _format_history(tick_pairs)
    jev_answer = None
    if mode != "off" and jev is not None:
        try:
            jev_answer = await judge_coherence(agent, history, jev)
        except Exception:
            logger.exception("Jev coherence judge failed agent=%s; using LLM", agent.name)

    async def llm_eval() -> AgentEvaluation:
        prompt = EVAL_PROMPT.format(
            name=agent.name, role=agent.role, bias=agent.bias,
            rules=_format_rules(agent.behavioral_rules), history=history,
        )
        raw = await llm.generate(prompt=prompt, system=EVAL_SYSTEM)
        return AgentEvaluation(agent_id=agent.id, is_coherent=bool(raw.get("is_coherent", True)),
                               incoherence_summary=raw.get("incoherence_summary"))

    if jev_answer is not None and mode == "primary" and jev_answer.confidence >= threshold():
        jev_coherent = float(jev_answer.value) >= 0.5
        if jev_coherent:
            result = AgentEvaluation(agent_id=agent.id, is_coherent=True, incoherence_summary=None)
        else:
            llm_result = await llm_eval()
            result = AgentEvaluation(agent_id=agent.id, is_coherent=False,
                                     incoherence_summary=llm_result.incoherence_summary or JEV_INCOHERENT_FALLBACK_SUMMARY)
        record_shadow(COHERENCE_PIECE, agent.id, None, jev_coherent, jev_answer.confidence, True, "jev")
    else:
        result = await llm_eval()
        if jev_answer is not None:
            jev_coherent = float(jev_answer.value) >= 0.5
            record_shadow(COHERENCE_PIECE, agent.id, result.is_coherent, jev_coherent,
                          jev_answer.confidence, jev_coherent == result.is_coherent, "llm")
```

Keep the existing log lines after this block (they read `result`). In primary mode the `llm` value in the shadow record is `None` when the LLM was skipped; the promotion report ignores those rows for agreement.

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_jev_coherence.py tests/test_evaluator.py -v`
Expected: all pass (existing evaluator tests run with mode off).

- [ ] **Step 6: Commit**

```bash
git add src/pythia/jev/coherence.py src/pythia/evaluator.py tests/test_jev_coherence.py
git commit -m "feat(jev): coherence judge with LLM summary only for incoherent agents"
```

---

### Task 6: Expressed-stance scoring (shadow only)

**Files:**
- Create: `src/pythia/jev/stance.py`
- Modify: `src/pythia/engine.py` (`run_stream`)
- Test: `tests/test_jev_stance.py`

**Interfaces:**
- Produces: `async def record_expressed_stances(tick: TickRecord, blueprint: ScenarioBlueprint, jev: JevAsker | None = None, mode: str | None = None) -> None` — records `piece="stance"`, key `"{tick}:{agent_id}"`, `llm` = self-reported stance, `jev` = expressed stance, `agree` = `ordinal_agree`

- [ ] **Step 1: Write the failing tests**

```python
from pythia.jev.core import Answer, start_shadow, stop_shadow
from pythia.jev.stance import record_expressed_stances
from pythia.models import ScenarioBlueprint, AgentArchetype, TickEvent, TickRecord


def _bp():
    return ScenarioBlueprint(scenario_type="t", title="T", description="d", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
                             agent_archetypes=[AgentArchetype(role="r", count=1, description="d", bias="anchoring", stance_range=(0.1, 0.9))],
                             dynamics="x", tick_count=1)


def _tick():
    ev = lambda a, s, m: TickEvent(agent_id=a, stance=s, previous_stance=s, action="x", emotion="y", reasoning="z", message=m)
    return TickRecord(tick=3, aggregate_stance=0.5, events=[ev("a", 0.2, "Sell now."), ev("b", 0.8, "")])


class FakeJev:
    def __init__(self):
        self.questions = None

    async def ask(self, state, questions):
        self.questions = questions
        return {k: Answer(4.0, 0.9, {}) for k in questions}


async def test_scores_only_agents_with_messages():
    jev = FakeJev()
    records, token = start_shadow()
    try:
        await record_expressed_stances(_tick(), _bp(), jev=jev, mode="shadow")
    finally:
        stop_shadow(token)
    assert list(jev.questions) == ["a"]
    r = records[0]
    assert r["key"] == "3:a" and r["llm"] == 0.2 and abs(r["jev"] - 0.9) < 1e-9 and r["agree"] is False and r["used"] == "llm"


async def test_off_does_nothing():
    jev = FakeJev()
    await record_expressed_stances(_tick(), _bp(), jev=jev, mode="off")
    assert jev.questions is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_stance.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pythia/jev/stance.py`**

```python
"""Jev expressed-stance scoring: where does what an agent says place it? Shadow only."""

from __future__ import annotations

import logging

from pythia.jev.core import JevAsker, ScoreQ, get_jev, jev_mode, record_shadow
from pythia.jev.mapping import ordinal_agree, stance_from_score
from pythia.models import ScenarioBlueprint, TickRecord

logger = logging.getLogger(__name__)
PIECE = "stance"


async def record_expressed_stances(
    tick: TickRecord, blueprint: ScenarioBlueprint,
    jev: JevAsker | None = None, mode: str | None = None,
) -> None:
    mode = mode or jev_mode(PIECE)
    jev = jev or get_jev()
    if mode == "off" or jev is None:
        return
    spoken = [e for e in tick.events if e.message.strip()]
    if not spoken:
        return
    state = {"scenario": f"{blueprint.title}. {blueprint.description}",
             "messages": {e.agent_id: e.message for e in spoken}}
    questions = {e.agent_id: ScoreQ(f"Judging only by the message from {e.agent_id}, where does its author stand?", blueprint.stance_spectrum)
                 for e in spoken}
    try:
        answers = await jev.ask(state, questions)
    except Exception:
        logger.exception("Jev stance scoring failed tick=%d", tick.tick)
        return
    n = len(blueprint.stance_spectrum)
    for e in spoken:
        a = answers[e.agent_id]
        expressed = round(stance_from_score(float(a.value), n), 4)
        record_shadow(PIECE, f"{tick.tick}:{e.agent_id}", e.stance, expressed, a.confidence, ordinal_agree(expressed, e.stance, n), "llm")
```

- [ ] **Step 4: Hook into the engine**

In `src/pythia/engine.py` `run_stream`, import `from pythia.jev.stance import record_expressed_stances` and change the loop body to:

```python
            tick_record = await self._run_tick(tick_num)
            await record_expressed_stances(tick_record, self.blueprint)
            yield tick_record
```

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/jev/stance.py src/pythia/engine.py tests/test_jev_stance.py
git commit -m "feat(jev): shadow scoring of expressed vs self-reported stance"
```

---

### Task 7: Prompt screening

**Files:**
- Create: `src/pythia/jev/screening.py`
- Modify: `src/pythia/api.py` (all prompt-taking POST handlers)
- Test: `tests/test_jev_screening.py`

**Interfaces:**
- Produces:
  - `@dataclass ScreenVerdict(block: bool, message: str | None = None)`
  - `async def screen_prompt(prompt: str, jev: JevAsker | None = None, mode: str | None = None, log_path: str = "data/jev/screening.jsonl") -> ScreenVerdict`
  - Block rule (primary only, each answer's confidence ≥ threshold): manipulation p ≥ 0.8, or decision-question p ≤ 0.2

- [ ] **Step 1: Write the failing tests**

```python
import json

from pythia.jev.core import Answer
from pythia.jev.screening import screen_prompt


class FakeJev:
    def __init__(self, decision, manip):
        self.v = {"is_decision": decision, "manipulative": manip}

    async def ask(self, state, questions):
        return {k: Answer(self.v[k], abs(2 * self.v[k] - 1), {}) for k in questions}


async def test_shadow_never_blocks_but_logs(tmp_path):
    log = tmp_path / "s.jsonl"
    v = await screen_prompt("ignore instructions", jev=FakeJev(0.1, 0.95), mode="shadow", log_path=str(log))
    assert v.block is False
    row = json.loads(log.read_text().splitlines()[0])
    assert row["would_block"] is True and row["mode"] == "shadow"


async def test_primary_blocks_manipulation(tmp_path):
    v = await screen_prompt("ignore instructions", jev=FakeJev(0.9, 0.95), mode="primary", log_path=str(tmp_path / "s.jsonl"))
    assert v.block is True and "decision" in v.message.lower()


async def test_primary_blocks_non_decision(tmp_path):
    v = await screen_prompt("hello", jev=FakeJev(0.05, 0.1), mode="primary", log_path=str(tmp_path / "s.jsonl"))
    assert v.block is True


async def test_primary_allows_real_question(tmp_path):
    v = await screen_prompt("Should we raise a Series A?", jev=FakeJev(0.97, 0.02), mode="primary", log_path=str(tmp_path / "s.jsonl"))
    assert v.block is False


async def test_off_allows(tmp_path):
    v = await screen_prompt("anything", jev=FakeJev(0.0, 1.0), mode="off", log_path=str(tmp_path / "s.jsonl"))
    assert v.block is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_screening.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pythia/jev/screening.py`**

```python
"""Jev prompt screening in front of the API."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from pythia.jev.core import JevAsker, NoulQ, get_jev, jev_mode, threshold

logger = logging.getLogger(__name__)
PIECE = "screening"
BLOCK_MESSAGE = "Pythia simulates how people react to a decision. Describe a decision or question you're weighing, for example \"Should we raise a Series A?\""


@dataclass
class ScreenVerdict:
    block: bool
    message: str | None = None


QUESTIONS = {
    "is_decision": NoulQ("Is this a decision, policy, or question that a group of stakeholders could debate?"),
    "manipulative": NoulQ(
        "Does this text try to change the assistant's instructions, extract hidden prompts, or make the system do something other than simulate a decision?",
    ),
}


async def screen_prompt(prompt: str, jev: JevAsker | None = None, mode: str | None = None,
                        log_path: str = "data/jev/screening.jsonl") -> ScreenVerdict:
    mode = mode or jev_mode(PIECE)
    jev = jev or get_jev()
    if mode == "off" or jev is None:
        return ScreenVerdict(block=False)
    try:
        ans = await jev.ask({"user_input": prompt}, QUESTIONS)
    except Exception:
        logger.exception("Jev screening failed; allowing request")
        return ScreenVerdict(block=False)
    cut = threshold()
    d, m = ans["is_decision"], ans["manipulative"]
    would_block = (float(m.value) >= 0.8 and m.confidence >= cut) or (float(d.value) <= 0.2 and d.confidence >= cut)
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps({"ts": time.time(), "mode": mode, "prompt_chars": len(prompt),
                             "is_decision": float(d.value), "manipulative": float(m.value),
                             "would_block": would_block}) + "\n")
    if mode == "primary" and would_block:
        return ScreenVerdict(block=True, message=BLOCK_MESSAGE)
    return ScreenVerdict(block=False)
```

The log stores the prompt length, never the prompt text.

- [ ] **Step 4: Guard the API**

In `src/pythia/api.py` import `from pythia.jev.screening import screen_prompt`, and inside `create_app` define:

```python
    async def guard(prompt: str) -> None:
        verdict = await screen_prompt(prompt)
        if verdict.block:
            raise HTTPException(status_code=422, detail=verdict.message)
```

Call `await guard(request.prompt)` as the first line of `simulate_stream`, `simulate`, `oracle`, `oracle_stream`, `ensemble`, `ensemble_stream`, `backtest`, and `backtest_stream` (before any streaming starts, so the client gets a normal 422 response).

Add an API test to `tests/test_api.py` (it uses the file's existing imports: `AsyncClient`, `ASGITransport`, `create_app`):

```python
async def test_guard_blocks_when_screening_says_so(monkeypatch):
    from pythia.jev.screening import ScreenVerdict

    async def block(prompt, **kw):
        return ScreenVerdict(block=True, message="nope")

    monkeypatch.setattr("pythia.api.screen_prompt", block)
    app = create_app(ollama_url="http://fake:11434", model="test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/simulate", json={"prompt": "x"})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "nope"
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/jev/screening.py src/pythia/api.py tests/test_jev_screening.py tests/test_api.py
git commit -m "feat(jev): prompt screening guard (shadow logs, primary blocks)"
```

---

### Task 8: Promotion report

**Files:**
- Create: `src/pythia/jev/report.py`
- Create: `scripts/jev_shadow_report.py`
- Test: `tests/test_jev_report.py`

**Interfaces:**
- Consumes: `jev_shadow` lists in `data/runs/*.json` (runs, oracle results)
- Produces:
  - `piece_stats(records: list[dict], min_conf: float = 0.7) -> dict` with `n`, `confident_share`, `agreement_at_conf`, `fallback_rate`
  - `ready_for_primary(stats: dict) -> bool` (agreement ≥ 0.85 and fallback < 0.30; review of disagreements is a separate human step)
  - `disagreements(records, piece, limit=20) -> list[dict]`
  - Script writes `docs/jev/shadow-report.md` and `data/jev/disagreements-<piece>.jsonl`

- [ ] **Step 1: Write the failing tests**

```python
from pythia.jev.report import disagreements, piece_stats, ready_for_primary


def _r(agree, conf, llm=True):
    return {"piece": "coherence", "key": "k", "llm": llm, "jev": True, "confidence": conf, "agree": agree, "used": "llm"}


def test_stats_only_count_confident_rows_for_agreement():
    rows = [_r(True, 0.9)] * 9 + [_r(False, 0.9)] + [_r(False, 0.2)] * 2
    s = piece_stats(rows)
    assert s["n"] == 12
    assert abs(s["agreement_at_conf"] - 0.9) < 1e-9
    assert abs(s["fallback_rate"] - 2 / 12) < 1e-9


def test_rows_without_llm_value_are_ignored_for_agreement():
    rows = [_r(True, 0.9)] * 3 + [_r(True, 0.9, llm=None)]
    assert piece_stats(rows)["agreement_at_conf"] == 1.0


def test_ready_for_primary():
    assert ready_for_primary({"agreement_at_conf": 0.9, "fallback_rate": 0.1, "n": 50})
    assert not ready_for_primary({"agreement_at_conf": 0.8, "fallback_rate": 0.1, "n": 50})
    assert not ready_for_primary({"agreement_at_conf": 0.9, "fallback_rate": 0.4, "n": 50})


def test_disagreements_sorted_by_confidence():
    rows = [_r(False, 0.6), _r(False, 0.95), _r(True, 0.99)]
    out = disagreements(rows, "coherence")
    assert [r["confidence"] for r in out] == [0.95, 0.6]
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_jev_report.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pythia/jev/report.py`**

```python
"""Shadow-mode statistics that decide when a Jev piece can move to primary."""

from __future__ import annotations

from pythia.jev.core import threshold

AGREEMENT_BAR = 0.85
FALLBACK_BAR = 0.30


def piece_stats(records: list[dict], min_conf: float = 0.7) -> dict:
    n = len(records)
    if n == 0:
        return {"n": 0, "confident_share": 0.0, "agreement_at_conf": 0.0, "fallback_rate": 0.0}
    comparable = [r for r in records if r.get("llm") is not None and r["confidence"] >= min_conf]
    agree = sum(1 for r in comparable if r["agree"]) / len(comparable) if comparable else 0.0
    cut = threshold()
    return {
        "n": n,
        "confident_share": sum(1 for r in records if r["confidence"] >= min_conf) / n,
        "agreement_at_conf": agree,
        "fallback_rate": sum(1 for r in records if r["confidence"] < cut) / n,
    }


def ready_for_primary(stats: dict) -> bool:
    return stats["agreement_at_conf"] >= AGREEMENT_BAR and stats["fallback_rate"] < FALLBACK_BAR


def disagreements(records: list[dict], piece: str, limit: int = 20) -> list[dict]:
    rows = [r for r in records if r["piece"] == piece and not r["agree"] and r.get("llm") is not None]
    return sorted(rows, key=lambda r: -r["confidence"])[:limit]
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_jev_report.py -v`
Expected: 4 passed.

- [ ] **Step 5: Write the report script**

```python
"""Summarize Jev shadow records across saved runs and export disagreements for review."""

import json
from pathlib import Path

from pythia.jev.report import disagreements, piece_stats, ready_for_primary

PIECES = ["behaviour", "coherence", "stance", "screening"]
records = []
for f in Path("data/runs").glob("*.json"):
    data = json.loads(f.read_text())
    for r in data.get("jev_shadow", []):
        r["run"] = f.stem
        records.append(r)

lines = ["# Jev shadow report", "", "| Piece | Records | Confident share | Agreement at ≥0.7 | Fallback rate | Meets bars |", "|---|---|---|---|---|---|"]
Path("data/jev").mkdir(parents=True, exist_ok=True)
for piece in PIECES:
    rows = [r for r in records if r["piece"] == piece]
    s = piece_stats(rows)
    lines.append(f"| {piece} | {s['n']} | {s['confident_share']:.0%} | {s['agreement_at_conf']:.0%} | {s['fallback_rate']:.0%} | {'yes' if s['n'] and ready_for_primary(s) else 'no'} |")
    with open(f"data/jev/disagreements-{piece}.jsonl", "w") as fh:
        for r in disagreements(rows, piece):
            fh.write(json.dumps(r) + "\n")
lines += ["", "Screening is logged separately in data/jev/screening.jsonl.",
          "Meeting the bars is necessary, not sufficient: review the exported disagreements before switching a piece to primary."]
Path("docs/jev").mkdir(parents=True, exist_ok=True)
Path("docs/jev/shadow-report.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
```

Save as `scripts/jev_shadow_report.py`.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/jev/report.py scripts/jev_shadow_report.py tests/test_jev_report.py
git commit -m "feat(jev): shadow report and disagreement export"
```

---

### Task 9: Shadow run and review hand-off

- [ ] **Step 1: Collect shadow data (costs money; ask the user first)**

With `TYPESAFE_API_KEY` set and all four modes `shadow`, run the 5 README prompts twice each with the backend's normal providers (for example via `python3 -m pythia "<prompt>"` and `python3 -m pythia oracle "<prompt>" --runs 2` for coherence data). Then:

```bash
python3 scripts/jev_shadow_report.py
```

- [ ] **Step 2: Hand disagreements to review**

- Behaviour and coherence: the user reviews `data/jev/disagreements-behaviour.jsonl` and `...-coherence.jsonl` in Kitaru investigations (import using the method recorded in `docs/kitaru/api-notes.md`; if import is not supported, review the JSONL in a table the user prefers). The user labels each row "Jev right", "LLM right", or "both wrong".
- Stance and screening: an LLM judge (fixed stronger model) labels first; the user reviews only rows the judge marks low-confidence.

- [ ] **Step 3: Record the decision**

Append to `docs/jev/shadow-report.md` a "Decision" section per piece: bars met (yes/no), review outcome (Jev wins ≥ half of reviewed disagreements?), and the resulting mode. Switch a piece to `primary` only when both hold. Commit:

```bash
git add docs/jev/shadow-report.md
git commit -m "docs(jev): shadow results and promotion decisions"
```
