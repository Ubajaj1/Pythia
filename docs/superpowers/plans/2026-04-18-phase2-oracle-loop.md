# Phase 2 — Oracle Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the self-improving loop — simulate → evaluate reasoning coherence → amend behavioral rules additively → re-run — without requiring ground truth.

**Architecture:** 4 new Python modules wired around the existing `SimulationEngine`. The evaluator grades each agent's *reasoning coherence* (does stated reasoning explain the action?), not archetype conformity. The temple rewrites rules additively (adds nuance, never removes). The oracle loop orchestrates N iterations, skipping re-analysis on subsequent runs. A new API endpoint + CLI subcommand expose the loop, and the UI displays real accuracy data from it.

**Tech Stack:** Python + Pydantic + httpx + FastAPI (all existing), pytest-asyncio (existing), React + Vite + Vitest (existing)

---

## File Map

**New Python files:**
- `src/pythia/evaluator.py` — LLM-based reasoning coherence check, one call per agent
- `src/pythia/temple.py` — additive `behavioral_rules` amendment for failing agents
- `src/pythia/oracle_loop.py` — N-run loop: analyze → generate → [run → evaluate → amend] × N
- `tests/test_evaluator.py`
- `tests/test_temple.py`
- `tests/test_oracle_loop.py`

**Modified Python files:**
- `src/pythia/models.py` — add `AgentEvaluation`, `OracleRunRecord`, `OracleLoopResult`, `OracleRequest`
- `src/pythia/api.py` — add `POST /api/oracle`
- `src/pythia/__main__.py` — add `oracle` subcommand
- `tests/test_api.py` — add oracle endpoint test

**New/Modified UI files:**
- `src/ui/src/simulation/scenarios.js` — add `scenarioFromOracleResult()`
- `src/ui/src/simulation/useSimulation.js` — add `useOracleSimulation()` hook
- `src/ui/src/App.jsx` — add `OracleSimulation` component + oracle state
- `src/ui/src/components/InputBar.jsx` — add "Run Oracle Loop" button
- `src/ui/src/simulation/scenarios.test.js` — add `scenarioFromOracleResult` test

---

## Task 1: Oracle Loop Models

**Files:**
- Modify: `src/pythia/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for new models**

Add to `tests/test_models.py`:

```python
from pythia.models import (
    AgentEvaluation, OracleRunRecord, OracleLoopResult, OracleRequest,
    RunResult, RunSummary, ScenarioInfo, AgentInfo, BiggestShift,
    TickRecord, TickEvent, AgentEvaluation,
)


class TestAgentEvaluation:
    def test_coherent_evaluation(self):
        e = AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None)
        assert e.agent_id == "a1"
        assert e.is_coherent is True
        assert e.incoherence_summary is None

    def test_incoherent_evaluation_requires_summary(self):
        e = AgentEvaluation(
            agent_id="a1", is_coherent=False,
            incoherence_summary="Agent said sell but stance increased",
        )
        assert e.is_coherent is False
        assert e.incoherence_summary is not None


class TestOracleRequest:
    def test_defaults(self):
        req = OracleRequest(prompt="Test")
        assert req.max_runs == 5
        assert req.context is None

    def test_max_runs_clamped(self):
        import pytest
        with pytest.raises(Exception):
            OracleRequest(prompt="Test", max_runs=0)
        with pytest.raises(Exception):
            OracleRequest(prompt="Test", max_runs=11)


class TestOracleLoopResult:
    def _make_run_result(self):
        return RunResult(
            run_id="r1",
            scenario=ScenarioInfo(input="t", type="m", title="T", stance_spectrum=["a","b","c","d","e"]),
            agents=[AgentInfo(id="a1", name="A", role="r", persona="p", bias="b", initial_stance=0.5)],
            ticks=[TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.5, previous_stance=0.5, action="hold", emotion="calm", reasoning="ok", message="ok"),
            ], aggregate_stance=0.5)],
            summary=RunSummary(
                total_ticks=1, final_aggregate_stance=0.5,
                biggest_shift=BiggestShift(agent_id="a1", from_stance=0.5, to_stance=0.5, reason=""),
                consensus_reached=True,
            ),
        )

    def test_coherence_history_matches_runs(self):
        run_record = OracleRunRecord(
            run_number=1,
            result=self._make_run_result(),
            evaluations=[AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None)],
            coherence_score=1.0,
            amended_agent_ids=[],
        )
        result = OracleLoopResult(
            prompt="test",
            runs=[run_record],
            coherence_history=[1.0],
        )
        assert len(result.coherence_history) == len(result.runs)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && source .venv/bin/activate && pytest tests/test_models.py -k "Oracle or AgentEvaluation" -v
```

Expected: `ImportError` — `AgentEvaluation` not defined yet

- [ ] **Step 3: Add new models to models.py**

At the end of `src/pythia/models.py`, after `class SimulateRequest`, add:

```python
# --- Oracle Loop ---

class AgentEvaluation(BaseModel):
    agent_id: str
    is_coherent: bool
    incoherence_summary: str | None = None


class OracleRunRecord(BaseModel):
    run_number: int
    result: RunResult
    evaluations: list[AgentEvaluation]
    coherence_score: float
    amended_agent_ids: list[str]


class OracleLoopResult(BaseModel):
    prompt: str
    runs: list[OracleRunRecord]
    coherence_history: list[float]


class OracleRequest(BaseModel):
    prompt: str
    context: str | None = None
    max_runs: int = Field(default=5, ge=1, le=10)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -k "Oracle or AgentEvaluation" -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pythia/models.py tests/test_models.py
git commit -m "feat: add oracle loop models — AgentEvaluation, OracleRunRecord, OracleLoopResult, OracleRequest"
```

---

## Task 2: Evaluator

**Files:**
- Create: `src/pythia/evaluator.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_evaluator.py`:

```python
"""Tests for the agent reasoning evaluator."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.evaluator import evaluate_agent, evaluate_run
from pythia.models import (
    Agent, AgentEvaluation, RunResult, ScenarioInfo, AgentInfo,
    TickEvent, TickRecord, RunSummary, BiggestShift,
)


def make_agent(agent_id="agent-a", rules=None):
    return Agent(
        id=agent_id, name="Agent A", role="trader",
        persona="Cautious trader.", bias="loss_aversion",
        initial_stance=0.3,
        behavioral_rules=rules or ["Sells on bad news"],
    )


def make_tick_events(agent_id="agent-a", n=3):
    return [
        (i + 1, TickEvent(
            agent_id=agent_id,
            stance=0.3 - i * 0.02,
            previous_stance=0.3 - (i - 1) * 0.02 if i > 0 else 0.3,
            action="sell", emotion="anxious",
            reasoning=f"Bad signals at tick {i + 1}",
            message="Selling.", influence_target=None,
        ))
        for i in range(n)
    ]


def make_run_result(agent_ids=("agent-a", "agent-b")):
    tick_records = [
        TickRecord(
            tick=1,
            events=[
                TickEvent(
                    agent_id=aid, stance=0.3, previous_stance=0.3,
                    action="hold", emotion="neutral", reasoning="ok",
                    message="ok", influence_target=None,
                )
                for aid in agent_ids
            ],
            aggregate_stance=0.5,
        )
    ]
    return RunResult(
        run_id="run_test",
        scenario=ScenarioInfo(
            input="test", type="market", title="Test",
            stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        ),
        agents=[
            AgentInfo(id=aid, name=f"Agent {aid}", role="trader",
                      persona="p", bias="b", initial_stance=0.5)
            for aid in agent_ids
        ],
        ticks=tick_records,
        summary=RunSummary(
            total_ticks=1, final_aggregate_stance=0.5,
            biggest_shift=BiggestShift(
                agent_id="agent-a", from_stance=0.3, to_stance=0.3, reason="",
            ),
            consensus_reached=True,
        ),
    )


class TestEvaluateAgent:
    async def test_coherent_agent_returns_is_coherent_true(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent()
        tick_pairs = make_tick_events()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.agent_id == "agent-a"
        assert result.is_coherent is True
        assert result.incoherence_summary is None

    async def test_incoherent_agent_returns_is_coherent_false(self):
        llm = FakeLLMClient(responses=[{
            "is_coherent": False,
            "incoherence_summary": "Agent claimed loss-aversion but bought with no explanation",
        }])
        agent = make_agent()
        tick_pairs = make_tick_events()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.is_coherent is False
        assert result.incoherence_summary is not None

    async def test_eval_prompt_contains_agent_behavioral_rules(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent(rules=["Never panic sell", "Always check fundamentals"])
        tick_pairs = make_tick_events()

        await evaluate_agent(agent, tick_pairs, llm)

        assert "Never panic sell" in llm.calls[0]["prompt"]
        assert "Always check fundamentals" in llm.calls[0]["prompt"]

    async def test_eval_prompt_contains_tick_history(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None}
        ])
        agent = make_agent()
        tick_pairs = make_tick_events()

        await evaluate_agent(agent, tick_pairs, llm)

        assert "Bad signals at tick 1" in llm.calls[0]["prompt"]

    async def test_missing_is_coherent_in_response_defaults_to_true(self):
        llm = FakeLLMClient(responses=[{}])
        agent = make_agent()
        tick_pairs = make_tick_events()

        result = await evaluate_agent(agent, tick_pairs, llm)

        assert result.is_coherent is True


class TestEvaluateRun:
    async def test_returns_one_evaluation_per_agent(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": True, "incoherence_summary": None},
            {"is_coherent": True, "incoherence_summary": None},
        ])
        agents = [make_agent("agent-a"), make_agent("agent-b")]
        run_result = make_run_result(("agent-a", "agent-b"))

        evals = await evaluate_run(run_result, agents, llm)

        assert len(evals) == 2
        assert {e.agent_id for e in evals} == {"agent-a", "agent-b"}

    async def test_returns_list_of_agent_evaluations(self):
        llm = FakeLLMClient(responses=[
            {"is_coherent": False, "incoherence_summary": "Contradiction"},
            {"is_coherent": True, "incoherence_summary": None},
        ])
        agents = [make_agent("agent-a"), make_agent("agent-b")]
        run_result = make_run_result(("agent-a", "agent-b"))

        evals = await evaluate_run(run_result, agents, llm)

        assert all(isinstance(e, AgentEvaluation) for e in evals)
        failing = [e for e in evals if not e.is_coherent]
        assert len(failing) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_evaluator.py -v
```

Expected: `ModuleNotFoundError: No module named 'pythia.evaluator'`

- [ ] **Step 3: Create evaluator.py**

Create `src/pythia/evaluator.py`:

```python
"""Evaluator — grades each agent's reasoning coherence after a simulation run."""

from __future__ import annotations

import asyncio

from pythia.llm import LLMClient
from pythia.models import Agent, AgentEvaluation, RunResult, TickEvent


EVAL_SYSTEM = """\
You are evaluating whether an AI agent's reasoning is internally coherent.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON."""


EVAL_PROMPT = """\
Agent: {name} ({role})
Cognitive bias: {bias}

Behavioral rules:
{rules}

Agent's tick-by-tick history in this simulation:
{history}

Question: Was this agent's reasoning coherent?

Rules for judging:
- It is FINE for the agent to deviate from their archetype — people surprise us.
- It is FINE for the agent to change their mind across ticks.
- Flag as INCOHERENT only if:
  (a) The stated reasoning directly contradicts the action taken
  (b) The reasoning is self-contradictory within a single tick
  (c) There is NO reasoning given for a large stance shift (change > 0.3 with empty or generic reasoning)

Respond with ONLY this JSON:
{{"is_coherent": true, "incoherence_summary": null}}
or
{{"is_coherent": false, "incoherence_summary": "<one sentence describing what was incoherent>"}}"""


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def _format_history(tick_pairs: list[tuple[int, TickEvent]]) -> str:
    if not tick_pairs:
        return "(no history)"
    lines = []
    for tick_num, e in tick_pairs:
        delta = e.stance - e.previous_stance
        lines.append(
            f"Tick {tick_num}: stance {e.previous_stance:.2f}→{e.stance:.2f} ({delta:+.2f}), "
            f'action="{e.action}", reasoning="{e.reasoning}"'
        )
    return "\n".join(lines)


def _extract_agent_tick_pairs(
    run_result: RunResult, agent_id: str
) -> list[tuple[int, TickEvent]]:
    """Return [(tick_num, TickEvent)] for one agent across all ticks."""
    pairs = []
    for tick_record in run_result.ticks:
        for event in tick_record.events:
            if event.agent_id == agent_id:
                pairs.append((tick_record.tick, event))
    return pairs


async def evaluate_agent(
    agent: Agent,
    tick_pairs: list[tuple[int, TickEvent]],
    llm: LLMClient,
) -> AgentEvaluation:
    """Evaluate one agent's reasoning coherence. One LLM call."""
    prompt = EVAL_PROMPT.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        rules=_format_rules(agent.behavioral_rules),
        history=_format_history(tick_pairs),
    )
    raw = await llm.generate(prompt=prompt, system=EVAL_SYSTEM)
    return AgentEvaluation(
        agent_id=agent.id,
        is_coherent=bool(raw.get("is_coherent", True)),
        incoherence_summary=raw.get("incoherence_summary"),
    )


async def evaluate_run(
    run_result: RunResult,
    agents: list[Agent],
    llm: LLMClient,
) -> list[AgentEvaluation]:
    """Evaluate all agents in parallel. Returns one AgentEvaluation per agent."""
    tasks = [
        evaluate_agent(
            agent,
            _extract_agent_tick_pairs(run_result, agent.id),
            llm,
        )
        for agent in agents
    ]
    return list(await asyncio.gather(*tasks))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_evaluator.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pythia/evaluator.py tests/test_evaluator.py
git commit -m "feat: add evaluator — LLM-based reasoning coherence check per agent"
```

---

## Task 3: Temple of Learning

**Files:**
- Create: `src/pythia/temple.py`
- Create: `tests/test_temple.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_temple.py`:

```python
"""Tests for the Temple of Learning — behavioral rule amendment."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.temple import amend_agent
from pythia.models import Agent, AgentEvaluation, TickEvent


def make_agent():
    return Agent(
        id="agent-a", name="Agent A", role="trader",
        persona="Cautious trader.", bias="loss_aversion",
        initial_stance=0.3,
        behavioral_rules=["Sells on bad news", "Avoids leverage"],
    )


def make_tick_events():
    return [
        TickEvent(
            agent_id="agent-a", stance=0.85, previous_stance=0.3,
            action="buy aggressively", emotion="excited",
            reasoning="FOMO took over",
            message="All in.", influence_target=None,
        )
    ]


def make_incoherent_eval():
    return AgentEvaluation(
        agent_id="agent-a",
        is_coherent=False,
        incoherence_summary="Agent claimed loss-aversion but bought aggressively with no explanation",
    )


class TestAmendAgent:
    async def test_amended_agent_has_more_rules_than_original(self):
        llm = FakeLLMClient(responses=[{
            "new_rules": ["When FOMO overrides loss-aversion, explicitly state the triggering condition"]
        }])
        agent = make_agent()
        original_rule_count = len(agent.behavioral_rules)

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert len(amended.behavioral_rules) > original_rule_count

    async def test_amended_agent_preserves_all_original_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert "Sells on bad news" in amended.behavioral_rules
        assert "Avoids leverage" in amended.behavioral_rules

    async def test_new_rules_are_appended_not_prepended(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert amended.behavioral_rules[-1] == "New rule"

    async def test_identity_fields_unchanged(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert amended.id == "agent-a"
        assert amended.name == "Agent A"
        assert amended.bias == "loss_aversion"
        assert amended.initial_stance == 0.3

    async def test_temple_prompt_contains_incoherence_summary(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()
        evaluation = AgentEvaluation(
            agent_id="agent-a", is_coherent=False,
            incoherence_summary="Unique summary text for assertion",
        )

        await amend_agent(agent, evaluation, make_tick_events(), llm)

        assert "Unique summary text for assertion" in llm.calls[0]["prompt"]

    async def test_temple_prompt_contains_current_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["New rule"]}])
        agent = make_agent()

        await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert "Sells on bad news" in llm.calls[0]["prompt"]
        assert "Avoids leverage" in llm.calls[0]["prompt"]

    async def test_coherent_agent_returned_unchanged(self):
        llm = FakeLLMClient(responses=[])
        agent = make_agent()
        coherent_eval = AgentEvaluation(
            agent_id="agent-a", is_coherent=True, incoherence_summary=None,
        )

        amended = await amend_agent(agent, coherent_eval, make_tick_events(), llm)

        assert amended is agent
        assert len(llm.calls) == 0

    async def test_ignores_non_string_new_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": ["Valid rule", 42, None, "Another valid"]}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        added = amended.behavioral_rules[len(agent.behavioral_rules):]
        assert added == ["Valid rule", "Another valid"]

    async def test_empty_new_rules_returns_agent_with_same_rules(self):
        llm = FakeLLMClient(responses=[{"new_rules": []}])
        agent = make_agent()

        amended = await amend_agent(agent, make_incoherent_eval(), make_tick_events(), llm)

        assert amended.behavioral_rules == agent.behavioral_rules
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_temple.py -v
```

Expected: `ModuleNotFoundError: No module named 'pythia.temple'`

- [ ] **Step 3: Create temple.py**

Create `src/pythia/temple.py`:

```python
"""Temple of Learning — amends agent behavioral_rules additively after incoherence."""

from __future__ import annotations

from pythia.llm import LLMClient
from pythia.models import Agent, AgentEvaluation, TickEvent


TEMPLE_SYSTEM = """\
You are helping an AI simulation agent learn from its reasoning failures.
Respond with ONLY valid JSON — no markdown, no explanation outside the JSON."""


TEMPLE_PROMPT = """\
Agent: {name} ({role})
Cognitive bias: {bias}

Current behavioral rules:
{rules}

Why this agent's reasoning was flagged as incoherent:
{incoherence_summary}

Agent's action history in this run:
{history}

Task: Add 1-3 new behavioral rules that would prevent this incoherence in future runs.
Guidelines:
- DO NOT remove or restate existing rules.
- ADD rules that capture context-sensitive nuance or explain when the agent may deviate.
- The goal is richer, more honest reasoning — not forcing the agent to conform to its archetype.
- Example good rule: "When overriding loss-aversion instinct, explicitly state the triggering condition in reasoning."

Respond with ONLY this JSON:
{{"new_rules": ["rule 1", "rule 2"]}}"""


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def _format_history(tick_events: list[TickEvent]) -> str:
    if not tick_events:
        return "(no history)"
    lines = []
    for i, e in enumerate(tick_events, 1):
        delta = e.stance - e.previous_stance
        lines.append(
            f"Tick {i}: stance {e.previous_stance:.2f}→{e.stance:.2f} ({delta:+.2f}), "
            f'action="{e.action}", reasoning="{e.reasoning}"'
        )
    return "\n".join(lines)


async def amend_agent(
    agent: Agent,
    evaluation: AgentEvaluation,
    tick_events: list[TickEvent],
    llm: LLMClient,
) -> Agent:
    """Return agent with behavioral_rules augmented by amendment. Returns original if coherent."""
    if evaluation.is_coherent:
        return agent

    prompt = TEMPLE_PROMPT.format(
        name=agent.name,
        role=agent.role,
        bias=agent.bias,
        rules=_format_rules(agent.behavioral_rules),
        incoherence_summary=evaluation.incoherence_summary or "Reasoning did not explain action",
        history=_format_history(tick_events),
    )
    raw = await llm.generate(prompt=prompt, system=TEMPLE_SYSTEM)
    new_rules = [r for r in raw.get("new_rules", []) if isinstance(r, str)]

    return agent.model_copy(update={
        "behavioral_rules": agent.behavioral_rules + new_rules,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_temple.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pythia/temple.py tests/test_temple.py
git commit -m "feat: add temple — additive behavioral_rules amendment for incoherent agents"
```

---

## Task 4: Oracle Loop Orchestrator

**Files:**
- Create: `src/pythia/oracle_loop.py`
- Create: `tests/test_oracle_loop.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_oracle_loop.py`:

```python
"""Tests for the Oracle Loop orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch
from tests.conftest import FakeLLMClient
from pythia.oracle_loop import run_oracle_loop
from pythia.models import Agent, AgentEvaluation, OracleLoopResult


# --- Canned LLM responses (same format as test_orchestrator.py) ---

ANALYZER_RESPONSE = {
    "scenario_type": "market_event",
    "title": "Test Event",
    "description": "A test simulation",
    "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
    "agent_archetypes": [
        {"role": "trader", "count": 1, "description": "d", "bias": "loss_aversion", "stance_range": [0.2, 0.4]},
        {"role": "analyst", "count": 1, "description": "d", "bias": "anchoring", "stance_range": [0.6, 0.8]},
    ],
    "dynamics": "Test",
    "tick_count": 3,
}

GEN_PASS1_TRADER = {
    "agents": [{
        "id": "trader-t", "name": "Trader T", "role": "trader",
        "persona": "A trader.", "bias": "loss_aversion",
        "initial_stance": 0.2, "behavioral_rules": ["Sells on dips"],
    }]
}

GEN_PASS1_ANALYST = {
    "agents": [{
        "id": "analyst-a", "name": "Analyst A", "role": "analyst",
        "persona": "An analyst.", "bias": "anchoring",
        "initial_stance": 0.8, "behavioral_rules": ["Holds steady"],
    }]
}

GEN_PASS2 = {
    "relationships": {
        "trader-t": [{"target": "analyst-a", "type": "follows", "weight": 0.5}],
        "analyst-a": [{"target": "trader-t", "type": "respects", "weight": 0.3}],
    }
}

TICK_TRADER = {
    "stance": 0.28, "action": "sell", "emotion": "anxious",
    "reasoning": "Bad vibes", "message": "Selling.", "influence_target": "analyst-a",
}

TICK_ANALYST = {
    "stance": 0.72, "action": "hold", "emotion": "steady",
    "reasoning": "Fundamentals ok", "message": "Holding.", "influence_target": "trader-t",
}


def make_sim_responses():
    """1 analyze + 2 gen_pass1 + 1 gen_pass2 + 3 ticks × 2 agents = 10 responses."""
    return [
        ANALYZER_RESPONSE,
        GEN_PASS1_TRADER, GEN_PASS1_ANALYST,
        GEN_PASS2,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
    ]


def make_run2_responses():
    """Run 2 skips analyze+generate, only needs 3 ticks × 2 agents = 6 responses."""
    return [TICK_TRADER, TICK_ANALYST] * 3


ALL_COHERENT = [
    AgentEvaluation(agent_id="trader-t", is_coherent=True, incoherence_summary=None),
    AgentEvaluation(agent_id="analyst-a", is_coherent=True, incoherence_summary=None),
]

ONE_FAILING = [
    AgentEvaluation(agent_id="trader-t", is_coherent=False, incoherence_summary="Contradiction"),
    AgentEvaluation(agent_id="analyst-a", is_coherent=True, incoherence_summary=None),
]

AMENDED_TRADER = Agent(
    id="trader-t", name="Trader T", role="trader",
    persona="A trader.", bias="loss_aversion",
    initial_stance=0.2,
    behavioral_rules=["Sells on dips", "State reason when overriding default behavior"],
)


class TestRunOracleLoop:
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_stops_after_one_run_when_all_coherent(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert isinstance(result, OracleLoopResult)
        assert len(result.runs) == 1
        assert mock_eval.call_count == 1

    @patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock)
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_runs_twice_when_one_agent_fails_then_all_pass(
        self, mock_eval, mock_amend, tmp_path
    ):
        mock_eval.side_effect = [ONE_FAILING, ALL_COHERENT]
        mock_amend.return_value = AMENDED_TRADER
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert len(result.runs) == 2
        assert mock_amend.call_count == 1  # only trader-t failed

    @patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock)
    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_records_amended_agent_ids(self, mock_eval, mock_amend, tmp_path):
        mock_eval.side_effect = [ONE_FAILING, ALL_COHERENT]
        mock_amend.return_value = AMENDED_TRADER
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=5, runs_dir=str(tmp_path))

        assert result.runs[0].amended_agent_ids == ["trader-t"]
        assert result.runs[1].amended_agent_ids == []

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_coherence_history_length_equals_run_count(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=3, runs_dir=str(tmp_path))

        assert len(result.coherence_history) == len(result.runs)

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_coherence_score_is_fraction_of_coherent_agents(self, mock_eval, tmp_path):
        mock_eval.return_value = ONE_FAILING  # 1 of 2 failing = 0.5 coherent
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=1, runs_dir=str(tmp_path))

        assert result.runs[0].coherence_score == 0.5

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_respects_max_runs_limit(self, mock_eval, tmp_path):
        # Always failing — should stop at max_runs, not run forever
        mock_eval.return_value = ONE_FAILING
        # Need sim responses for max_runs=2: 10 + 6 = 16
        llm = FakeLLMClient(responses=make_sim_responses() + make_run2_responses())

        # Patch amend_agent to return unchanged agent (no extra LLM calls)
        with patch("pythia.oracle_loop.amend_agent", new_callable=AsyncMock) as mock_amend:
            mock_amend.return_value = AMENDED_TRADER
            result = await run_oracle_loop("Test event", llm, max_runs=2, runs_dir=str(tmp_path))

        assert len(result.runs) == 2

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_saves_each_run_json_to_disk(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("Test event", llm, max_runs=1, runs_dir=str(tmp_path))

        run_id = result.runs[0].result.run_id
        assert (tmp_path / f"{run_id}.json").exists()

    @patch("pythia.oracle_loop.evaluate_run", new_callable=AsyncMock)
    async def test_prompt_preserved_in_result(self, mock_eval, tmp_path):
        mock_eval.return_value = ALL_COHERENT
        llm = FakeLLMClient(responses=make_sim_responses())

        result = await run_oracle_loop("My unique prompt", llm, max_runs=1, runs_dir=str(tmp_path))

        assert result.prompt == "My unique prompt"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_oracle_loop.py -v
```

Expected: `ModuleNotFoundError: No module named 'pythia.oracle_loop'`

- [ ] **Step 3: Create oracle_loop.py**

Create `src/pythia/oracle_loop.py`:

```python
"""Oracle Loop — orchestrates multi-run simulate → evaluate → amend cycle."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pythia.analyzer import analyze_scenario
from pythia.config import RUNS_DIR
from pythia.engine import SimulationEngine
from pythia.evaluator import evaluate_run
from pythia.generator import generate_agents
from pythia.llm import LLMClient
from pythia.models import (
    AgentInfo,
    BiggestShift,
    OracleLoopResult,
    OracleRunRecord,
    RunResult,
    RunSummary,
    ScenarioBlueprint,
    ScenarioInfo,
    TickEvent,
    TickRecord,
)
from pythia.temple import amend_agent


def _build_run_result(
    run_num: int,
    prompt: str,
    blueprint: ScenarioBlueprint,
    agents: list,
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

    return result


def _group_tick_events(run_result: RunResult) -> dict[str, list[TickEvent]]:
    """Group TickEvents by agent_id across all ticks."""
    events: dict[str, list[TickEvent]] = {}
    for tick_record in run_result.ticks:
        for event in tick_record.events:
            events.setdefault(event.agent_id, []).append(event)
    return events


async def run_oracle_loop(
    prompt: str,
    llm: LLMClient,
    max_runs: int = 5,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> OracleLoopResult:
    """Run up to max_runs iterations of simulate → evaluate → amend.

    Stops early if all agents pass coherence evaluation.
    Re-uses blueprint and (amended) agents across runs — no re-analysis.
    """
    blueprint = await analyze_scenario(prompt, llm=llm, context=context)
    agents = await generate_agents(blueprint, llm=llm)

    run_records: list[OracleRunRecord] = []

    for run_num in range(1, max_runs + 1):
        engine = SimulationEngine(blueprint=blueprint, agents=agents, llm=llm)
        ticks = await engine.run()
        run_result = _build_run_result(run_num, prompt, blueprint, agents, ticks, runs_dir)

        evaluations = await evaluate_run(run_result, agents, llm)
        coherence_score = sum(1 for e in evaluations if e.is_coherent) / len(evaluations)
        failing = [e for e in evaluations if not e.is_coherent]

        run_records.append(OracleRunRecord(
            run_number=run_num,
            result=run_result,
            evaluations=evaluations,
            coherence_score=round(coherence_score, 4),
            amended_agent_ids=[e.agent_id for e in failing],
        ))

        if not failing:
            break

        if run_num < max_runs:
            tick_events_by_agent = _group_tick_events(run_result)
            amended_agents = []
            for agent in agents:
                failing_eval = next((e for e in failing if e.agent_id == agent.id), None)
                if failing_eval:
                    amended = await amend_agent(
                        agent,
                        failing_eval,
                        tick_events_by_agent.get(agent.id, []),
                        llm,
                    )
                    amended_agents.append(amended)
                else:
                    amended_agents.append(agent)
            agents = amended_agents

    return OracleLoopResult(
        prompt=prompt,
        runs=run_records,
        coherence_history=[r.coherence_score for r in run_records],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_oracle_loop.py -v
```

Expected: All PASS

- [ ] **Step 5: Run all Python tests to check for regressions**

```bash
pytest tests/ -v
```

Expected: All 47 existing tests + new oracle_loop tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/pythia/oracle_loop.py tests/test_oracle_loop.py
git commit -m "feat: add oracle_loop — multi-run simulate→evaluate→amend orchestrator"
```

---

## Task 5: API + CLI Wiring

**Files:**
- Modify: `src/pythia/api.py`
- Modify: `src/pythia/__main__.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing API test**

Add to `tests/test_api.py`:

```python
from pythia.models import (
    RunResult, RunSummary, ScenarioInfo, AgentInfo,
    BiggestShift, TickRecord, TickEvent,
    AgentEvaluation, OracleRunRecord, OracleLoopResult,
)


def make_mock_oracle_result() -> OracleLoopResult:
    run_result = make_mock_result()
    run_record = OracleRunRecord(
        run_number=1,
        result=run_result,
        evaluations=[
            AgentEvaluation(agent_id="a1", is_coherent=True, incoherence_summary=None),
        ],
        coherence_score=1.0,
        amended_agent_ids=[],
    )
    return OracleLoopResult(
        prompt="Test prompt",
        runs=[run_record],
        coherence_history=[1.0],
    )


class TestOracleEndpoint:
    @pytest.fixture
    def app(self):
        return create_app(ollama_url="http://fake:11434", model="test")

    async def test_oracle_returns_oracle_loop_result(self, app):
        mock_result = make_mock_oracle_result()
        with patch("pythia.api.run_oracle_loop", new_callable=AsyncMock, return_value=mock_result):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/oracle",
                    json={"prompt": "Test prompt", "max_runs": 3},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompt"] == "Test prompt"
        assert len(data["runs"]) == 1
        assert data["coherence_history"] == [1.0]

    async def test_oracle_requires_prompt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/oracle", json={})
        assert resp.status_code == 422

    async def test_oracle_max_runs_validated(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/oracle", json={"prompt": "test", "max_runs": 0})
        assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -k "Oracle" -v
```

Expected: FAIL — `patch target 'pythia.api.run_oracle_loop' does not exist`

- [ ] **Step 3: Add oracle endpoint to api.py**

In `src/pythia/api.py`, add the import at the top:

```python
from pythia.models import SimulateRequest, OracleRequest
from pythia.oracle_loop import run_oracle_loop
```

Replace the existing imports block (lines 1-14) with:

```python
"""FastAPI server for Pythia."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL, RUNS_DIR
from pythia.llm import OllamaClient
from pythia.models import OracleRequest, SimulateRequest
from pythia.oracle_loop import run_oracle_loop
from pythia.orchestrator import run_simulation
```

Add the oracle endpoint inside `create_app`, after the `/api/simulate` endpoint:

```python
    @app.post("/api/oracle")
    async def oracle(request: OracleRequest) -> dict:
        result = await run_oracle_loop(
            prompt=request.prompt,
            context=request.context,
            max_runs=request.max_runs,
            llm=llm,
            runs_dir=runs_dir,
        )
        return result.model_dump(mode="json")
```

- [ ] **Step 4: Run API tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: All PASS

- [ ] **Step 5: Add oracle subcommand to CLI**

In `src/pythia/__main__.py`, add after `_run()`:

```python
async def _run_oracle(args: argparse.Namespace) -> None:
    from pythia.llm import OllamaClient
    from pythia.oracle_loop import run_oracle_loop

    llm = OllamaClient(base_url=args.ollama_url, model=args.model)
    try:
        oracle_result = await run_oracle_loop(
            prompt=args.prompt,
            context=args.context,
            max_runs=args.runs,
            llm=llm,
            runs_dir=args.runs_dir,
        )
        print(f"\n{'═' * 3} PYTHIA ORACLE — {oracle_result.runs[0].result.scenario.title} {'═' * 3}")
        print(f"Ran {len(oracle_result.runs)} simulation(s)\n")
        for record in oracle_result.runs:
            score_pct = round(record.coherence_score * 100)
            amended = ", ".join(record.amended_agent_ids) or "none"
            print(f"  Run {record.run_number}: coherence {score_pct}%  |  amended: {amended}")
        print(f"\nFinal coherence: {round(oracle_result.coherence_history[-1] * 100)}%")
    finally:
        await llm.close()
```

In `main()`, add the oracle subparser before `args = parser.parse_args()`:

```python
    # python -m pythia oracle "prompt"
    oracle_parser = subparsers.add_parser("oracle", help="Run oracle loop (multi-run self-improving simulation)")
    oracle_parser.add_argument("prompt", help="Decision or question to simulate")
    oracle_parser.add_argument("--runs", type=int, default=5, help="Maximum number of simulation runs")
    oracle_parser.add_argument("--context", default=None, help="Additional context paragraph")
```

In the `main()` dispatch block, add:

```python
    elif args.command == "oracle":
        asyncio.run(_run_oracle(args))
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/pythia/api.py src/pythia/__main__.py tests/test_api.py
git commit -m "feat: expose oracle loop via POST /api/oracle and python -m pythia oracle subcommand"
```

---

**Backend complete checkpoint.** The oracle loop is fully implemented and tested. You can verify it manually:
```bash
source .venv/bin/activate
python -m pythia oracle "Fed raises rates 50bps" --runs 2
```

---

## Task 6: UI Oracle Mode

**Files:**
- Modify: `src/ui/src/simulation/scenarios.js`
- Modify: `src/ui/src/simulation/useSimulation.js`
- Modify: `src/ui/src/App.jsx`
- Modify: `src/ui/src/components/InputBar.jsx`
- Modify: `src/ui/src/simulation/scenarios.test.js`

- [ ] **Step 1: Write failing test for scenarioFromOracleResult**

Add to `src/ui/src/simulation/scenarios.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { getScenario, scenarioFromRunResult, scenarioFromOracleResult } from './scenarios'

// ... existing tests stay as-is ...

describe('scenarioFromOracleResult', () => {
  const mockRunResult = {
    run_id: 'oracle_test_r1',
    scenario: { input: 'test', type: 'market', title: 'Oracle Test', stance_spectrum: ['vb','b','n','bu','vbu'] },
    agents: [
      { id: 'a1', name: 'Agent One', role: 'trader', persona: 'p', bias: 'loss_aversion', initial_stance: 0.3 },
      { id: 'a2', name: 'Agent Two', role: 'analyst', persona: 'p', bias: 'anchoring', initial_stance: 0.7 },
    ],
    ticks: [],
    summary: { total_ticks: 0, final_aggregate_stance: 0.5, biggest_shift: { agent_id: 'a1', from: 0.3, to: 0.3, reason: '' }, consensus_reached: false },
  }

  const mockOracleResult = {
    prompt: 'test prompt',
    coherence_history: [0.5, 0.75, 1.0],
    runs: [
      {
        run_number: 1,
        result: mockRunResult,
        evaluations: [],
        coherence_score: 0.5,
        amended_agent_ids: ['a1'],
      },
    ],
  }

  it('returns a scenario with protagonists from first run agents', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.protagonists).toHaveLength(2)
    expect(scenario.protagonists[0].id).toBe('a1')
    expect(scenario.protagonists[1].id).toBe('a2')
  })

  it('marks amended agents with amended flag', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.protagonists[0].amended).toBe(true)   // a1 was amended
    expect(scenario.protagonists[1].amended).toBe(false)  // a2 was not
  })

  it('returns coherenceHistory scaled to 0-100', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.coherenceHistory).toEqual([50, 75, 100])
  })

  it('includes ticks from first run', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.ticks).toBe(mockRunResult.ticks)
  })
})
```

- [ ] **Step 2: Run UI tests to verify they fail**

```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npm test -- --run
```

Expected: FAIL — `scenarioFromOracleResult is not a function`

- [ ] **Step 3: Add scenarioFromOracleResult to scenarios.js**

Add at the end of `src/ui/src/simulation/scenarios.js`:

```js
export function scenarioFromOracleResult(oracleResult) {
  const firstRun = oracleResult.runs[0]
  const amendedIds = new Set(firstRun.amended_agent_ids)

  const protagonists = firstRun.result.agents.map((agent, i) => ({
    id: agent.id,
    name: agent.name,
    trait: agent.bias,
    color: AGENT_COLORS[i % AGENT_COLORS.length].color,
    glow: AGENT_COLORS[i % AGENT_COLORS.length].glow,
    amended: amendedIds.has(agent.id),
  }))

  const amendments = firstRun.result.agents.map(agent => [
    amendedIds.has(agent.id) ? 'Amending' : 'Recalibrating',
    `${agent.bias} rules...`,
  ])

  return {
    name: firstRun.result.scenario.title,
    protagonists,
    amendments,
    ticks: firstRun.result.ticks,
    agents: firstRun.result.agents,
    coherenceHistory: oracleResult.coherence_history.map(s => Math.round(s * 100)),
  }
}
```

- [ ] **Step 4: Run UI tests to verify they pass**

```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npm test -- --run
```

Expected: All PASS

- [ ] **Step 5: Add useOracleSimulation hook to useSimulation.js**

Add at the end of `src/ui/src/simulation/useSimulation.js`:

```js
export function useOracleSimulation(oracleScenario) {
  const sim = useApiSimulation(oracleScenario)
  return {
    ...sim,
    accuracyHistory: oracleScenario.coherenceHistory,
  }
}
```

- [ ] **Step 6: Add oracle mode to App.jsx**

Replace `src/ui/src/App.jsx` with:

```jsx
import { useState } from 'react'
import { useSimulation, useApiSimulation, useOracleSimulation } from './simulation/useSimulation'
import { getScenario, scenarioFromRunResult, scenarioFromOracleResult } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'
import InputBar       from './components/InputBar'

const DEFAULT_SCENARIO_ID = 'market-sentiment'

function SimulationView({ scenario, sim }) {
  const templeProtagonist = sim.templeIdx !== null
    ? scenario.protagonists[sim.templeIdx]
    : null

  const templeAmendment = sim.templeIdx !== null
    ? scenario.amendments[sim.templeIdx]
    : ['', '']

  return (
    <>
      <Header
        scenarioName={scenario.name}
        tick={sim.tick}
        run={sim.run}
        progressPercent={sim.progressPercent}
        onRestart={sim.restart}
      />

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Stage
          protagonists={scenario.protagonists}
          protoStates={sim.protoStates}
        />
        <Arena
          crowdStateIndex={sim.crowdStateIndex}
          crowdStateName={sim.crowdStateName}
        />
        <Temple
          protagonist={templeProtagonist}
          amendment={templeAmendment}
        />
      </div>

      <AccuracyCurve history={sim.accuracyHistory} />
    </>
  )
}

function MockSimulation() {
  const scenario = getScenario(DEFAULT_SCENARIO_ID)
  const sim = useSimulation(scenario.protagonists, scenario.amendments)
  return <SimulationView scenario={scenario} sim={sim} />
}

function ApiSimulation({ runResult }) {
  const scenario = scenarioFromRunResult(runResult)
  const sim = useApiSimulation(scenario)
  return <SimulationView scenario={scenario} sim={sim} />
}

function OracleSimulation({ oracleResult }) {
  const scenario = scenarioFromOracleResult(oracleResult)
  const sim = useOracleSimulation(scenario)
  return <SimulationView scenario={scenario} sim={sim} />
}

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [oracleResult, setOracleResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  function handleSimulationResult(result) {
    setOracleResult(null)
    setRunResult(result)
  }

  function handleOracleResult(result) {
    setRunResult(null)
    setOracleResult(result)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <InputBar
        onSimulationResult={handleSimulationResult}
        onOracleResult={handleOracleResult}
        isLoading={isLoading}
        setIsLoading={setIsLoading}
      />
      {isLoading ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A88C52', fontFamily: 'Playfair Display, serif', fontSize: '18px',
          fontStyle: 'italic',
        }}>
          The Oracle is deliberating...
        </div>
      ) : oracleResult ? (
        <OracleSimulation oracleResult={oracleResult} />
      ) : runResult ? (
        <ApiSimulation runResult={runResult} />
      ) : (
        <MockSimulation />
      )}
    </div>
  )
}
```

- [ ] **Step 7: Add oracle button to InputBar.jsx**

Replace `src/ui/src/components/InputBar.jsx` with:

```jsx
import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function InputBar({ onSimulationResult, onOracleResult, isLoading, setIsLoading }) {
  const [prompt, setPrompt] = useState('')
  const [context, setContext] = useState('')
  const [error, setError] = useState(null)

  async function handleSubmit(e, mode) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    const endpoint = mode === 'oracle' ? '/api/oracle' : '/api/simulate'
    const body = mode === 'oracle'
      ? { prompt: prompt.trim(), context: context.trim() || undefined, max_runs: 5 }
      : { prompt: prompt.trim(), context: context.trim() || undefined }

    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)

      const result = await resp.json()
      if (mode === 'oracle') {
        onOracleResult(result)
      } else {
        onSimulationResult(result)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const inputStyle = {
    background: '#0D0D0B',
    border: '1px solid #2a2a25',
    borderRadius: '4px',
    padding: '8px 12px',
    color: '#d4c9a8',
    fontFamily: 'Syne, sans-serif',
    fontSize: '13px',
  }

  return (
    <form style={{
      padding: '12px 20px',
      borderBottom: '1px solid #1a1a17',
      display: 'flex',
      gap: '10px',
      alignItems: 'center',
      background: '#111110',
    }}>
      <input
        type="text"
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        placeholder="Describe a decision... e.g. Fed raises rates 50bps"
        disabled={isLoading}
        style={{ ...inputStyle, flex: 1 }}
      />
      <input
        type="text"
        value={context}
        onChange={e => setContext(e.target.value)}
        placeholder="Optional context..."
        disabled={isLoading}
        style={{ ...inputStyle, width: '200px' }}
      />
      <button
        type="button"
        onClick={e => handleSubmit(e, 'simulate')}
        disabled={isLoading || !prompt.trim()}
        style={{
          background: isLoading ? '#3a3520' : '#A88C52',
          color: '#0D0D0B',
          border: 'none',
          borderRadius: '4px',
          padding: '8px 16px',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
          fontWeight: 600,
          cursor: isLoading ? 'wait' : 'pointer',
          whiteSpace: 'nowrap',
          opacity: (!prompt.trim() || isLoading) ? 0.5 : 1,
        }}
      >
        {isLoading ? 'Consulting...' : 'Consult the Oracle'}
      </button>
      <button
        type="button"
        onClick={e => handleSubmit(e, 'oracle')}
        disabled={isLoading || !prompt.trim()}
        style={{
          background: 'transparent',
          color: isLoading ? '#3a3520' : '#A88C52',
          border: '1px solid #A88C52',
          borderRadius: '4px',
          padding: '8px 16px',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
          fontWeight: 600,
          cursor: isLoading ? 'wait' : 'pointer',
          whiteSpace: 'nowrap',
          opacity: (!prompt.trim() || isLoading) ? 0.5 : 1,
        }}
      >
        {isLoading ? 'Consulting...' : 'Oracle Loop ↻'}
      </button>
      {error && (
        <span style={{ color: '#C08878', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </span>
      )}
    </form>
  )
}
```

- [ ] **Step 8: Run all UI tests**

```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npm test -- --run
```

Expected: All 18+ tests PASS

- [ ] **Step 9: Run all Python tests (sanity check)**

```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && source .venv/bin/activate && pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add src/ui/src/simulation/scenarios.js src/ui/src/simulation/useSimulation.js src/ui/src/App.jsx src/ui/src/components/InputBar.jsx src/ui/src/simulation/scenarios.test.js
git commit -m "feat: add oracle loop UI — real accuracy curve, Oracle Loop button, oracle simulation mode"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Temple triggered on incoherent reasoning | Task 2 (evaluator) |
| Amendment is additive (adds nuance, doesn't remove rules) | Task 3 (temple) |
| No ground truth required — coherence metric | Task 2 + 4 |
| Agents re-used across runs (no re-generation) | Task 4 (oracle_loop: analyze+generate called once) |
| Accuracy curve shows real data | Task 6 (useOracleSimulation overrides accuracyHistory) |
| CLI support | Task 5 |
| API endpoint | Task 5 |

**Placeholder scan:** None found.

**Type consistency check:**
- `AgentEvaluation` defined in Task 1, used in Tasks 2, 3, 4 — consistent
- `OracleLoopResult` defined in Task 1, returned from `run_oracle_loop` in Task 4, used in API Task 5 — consistent
- `evaluate_run(run_result, agents, llm)` — defined Task 2, called Task 4 — consistent
- `amend_agent(agent, evaluation, tick_events, llm)` — defined Task 3, called Task 4 — consistent
- `scenarioFromOracleResult` — defined Task 6 step 3, used Task 6 step 6 — consistent
- `useOracleSimulation(oracleScenario)` — defined Task 6 step 5, used Task 6 step 6 — consistent
