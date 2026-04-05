# Phase 1 — Simulation Backbone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python backend that takes a user prompt, generates LLM-powered agents via Ollama, runs a tick-by-tick opinion dynamics simulation, and outputs structured JSON — accessible via CLI and HTTP API, with a React input bar.

**Architecture:** Custom simulation engine (no OASIS/CAMEL-AI). Three-stage pipeline: Scenario Analyzer → Agent Generator → Simulation Engine. All LLM calls go through a thin Ollama HTTP client. FastAPI serves the React UI. Everything is async.

**Tech Stack:** Python 3.11+, FastAPI, httpx, Pydantic, Ollama (local LLM), React (existing Vite app)

**Spec:** `docs/superpowers/specs/2026-04-04-phase1-simulation-backbone-design.md`

**Task dependency graph:**
```
Task 1 (setup) → Task 2 (models) → Task 3 (LLM client) → Task 4 (analyzer)  ──┐
                                                         → Task 5 (generator) ──┤→ Task 7 (orchestrator + CLI) → Task 8 (API) → Task 9 (UI)
                                                         → Task 6 (engine)    ──┘
```
Tasks 4, 5, 6 can run in parallel.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/pythia/__init__.py`
- Create: `src/pythia/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `data/runs/.gitkeep`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pythia"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create src/pythia/__init__.py**

```python
"""Pythia — opinion dynamics simulation engine."""
```

- [ ] **Step 3: Create src/pythia/config.py**

```python
"""Pythia configuration defaults."""

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"
DEFAULT_TICK_COUNT = 20
RUNS_DIR = "data/runs"
```

- [ ] **Step 4: Create tests/__init__.py and tests/conftest.py**

`tests/__init__.py` — empty file.

`tests/conftest.py`:

```python
"""Shared test fixtures for Pythia tests."""

import json
from pythia.llm import LLMClient


class FakeLLMClient(LLMClient):
    """LLM client that returns canned responses for testing."""

    def __init__(self, responses: list[dict] | None = None):
        self.responses = list(responses) if responses else []
        self.calls: list[dict] = []

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        self.calls.append({"prompt": prompt, "system": system})
        if self.responses:
            return self.responses.pop(0)
        return {}
```

- [ ] **Step 5: Create data/runs/.gitkeep**

Empty file.

- [ ] **Step 6: Install in editable mode and verify**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`

Expected: Installs successfully, `python -c "import pythia"` works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/pythia/__init__.py src/pythia/config.py tests/__init__.py tests/conftest.py data/runs/.gitkeep
git commit -m "feat: scaffold Phase 1 Python backend — pyproject.toml, config, test fixtures"
```

---

### Task 2: Pydantic Models

**Files:**
- Create: `src/pythia/models.py`
- Create: `tests/test_models.py`

All JSON schemas from the spec defined as Pydantic models. These are the data contracts between every component.

- [ ] **Step 1: Write failing tests for all models**

Create `tests/test_models.py`:

```python
"""Tests for Pythia data models."""

import pytest
from pydantic import ValidationError
from pythia.models import (
    AgentArchetype,
    ScenarioBlueprint,
    Agent,
    Relationship,
    TickAction,
    TickEvent,
    TickRecord,
    RunResult,
    RunSummary,
    SimulateRequest,
)


class TestAgentArchetype:
    def test_valid_archetype(self):
        a = AgentArchetype(
            role="retail_investor",
            count=2,
            description="Individual investors",
            bias="loss_aversion",
            stance_range=(0.2, 0.4),
        )
        assert a.role == "retail_investor"
        assert a.count == 2
        assert a.stance_range == (0.2, 0.4)

    def test_stance_range_must_be_0_to_1(self):
        with pytest.raises(ValidationError):
            AgentArchetype(
                role="x", count=1, description="x",
                bias="x", stance_range=(-0.1, 0.5),
            )

    def test_stance_range_low_must_be_less_than_high(self):
        with pytest.raises(ValidationError):
            AgentArchetype(
                role="x", count=1, description="x",
                bias="x", stance_range=(0.8, 0.2),
            )


class TestScenarioBlueprint:
    def test_valid_blueprint(self):
        bp = ScenarioBlueprint(
            scenario_type="market_event",
            title="Fed Rate Hike",
            description="Rate hike simulation",
            stance_spectrum=["very bearish", "bearish", "neutral", "bullish", "very bullish"],
            agent_archetypes=[
                AgentArchetype(role="retail", count=2, description="d", bias="loss_aversion", stance_range=(0.2, 0.4)),
            ],
            dynamics="Herd behavior likely.",
            tick_count=20,
        )
        assert bp.scenario_type == "market_event"
        assert len(bp.stance_spectrum) == 5

    def test_stance_spectrum_must_have_5_labels(self):
        with pytest.raises(ValidationError):
            ScenarioBlueprint(
                scenario_type="x", title="x", description="x",
                stance_spectrum=["a", "b", "c"],
                agent_archetypes=[], dynamics="x", tick_count=20,
            )


class TestAgent:
    def test_valid_agent(self):
        a = Agent(
            id="retail-rachel",
            name="Retail Rachel",
            role="retail_investor",
            persona="A 34-year-old trader.",
            bias="loss_aversion",
            initial_stance=0.35,
            behavioral_rules=["Sells quickly when negative"],
            relationships=[],
        )
        assert a.id == "retail-rachel"
        assert a.initial_stance == 0.35

    def test_stance_clamped_to_0_1(self):
        with pytest.raises(ValidationError):
            Agent(
                id="x", name="x", role="x", persona="x",
                bias="x", initial_stance=1.5,
                behavioral_rules=[], relationships=[],
            )


class TestTickAction:
    def test_valid_action(self):
        ta = TickAction(
            stance=0.25,
            action="sell",
            emotion="panicking",
            reasoning="Everyone is dumping",
            message="I'm out.",
            influence_target="elias",
        )
        assert ta.stance == 0.25

    def test_stance_clamped(self):
        ta = TickAction(
            stance=1.8, action="buy", emotion="manic",
            reasoning="x", message="x", influence_target=None,
        )
        assert ta.stance == 1.0

    def test_negative_stance_clamped(self):
        ta = TickAction(
            stance=-0.3, action="sell", emotion="fear",
            reasoning="x", message="x", influence_target=None,
        )
        assert ta.stance == 0.0


class TestRunResult:
    def test_valid_run_result(self):
        result = RunResult(
            run_id="run_2026-04-04_001",
            scenario={
                "input": "Fed raises rates",
                "type": "market_event",
                "title": "Fed Rate Hike",
                "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
            },
            agents=[],
            ticks=[],
            summary=RunSummary(
                total_ticks=20,
                final_aggregate_stance=0.58,
                biggest_shift={"agent_id": "rachel", "from_stance": 0.35, "to_stance": 0.72, "reason": "x"},
                consensus_reached=False,
            ),
        )
        assert result.run_id == "run_2026-04-04_001"


class TestSimulateRequest:
    def test_valid_request(self):
        r = SimulateRequest(prompt="Fed raises rates 50bps")
        assert r.prompt == "Fed raises rates 50bps"
        assert r.context is None

    def test_with_context(self):
        r = SimulateRequest(prompt="Buy or rent?", context="I have 50k saved")
        assert r.context == "I have 50k saved"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && python -m pytest tests/test_models.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.models'`

- [ ] **Step 3: Implement all models**

Create `src/pythia/models.py`:

```python
"""Pydantic models for all Pythia data structures."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


# --- Scenario Analyzer output ---

class AgentArchetype(BaseModel):
    role: str
    count: int = Field(ge=1)
    description: str
    bias: str
    stance_range: tuple[float, float]

    @field_validator("stance_range")
    @classmethod
    def validate_stance_range(cls, v: tuple[float, float]) -> tuple[float, float]:
        low, high = v
        if not (0.0 <= low <= 1.0 and 0.0 <= high <= 1.0):
            raise ValueError("stance_range values must be between 0.0 and 1.0")
        if low >= high:
            raise ValueError("stance_range low must be less than high")
        return v


class ScenarioBlueprint(BaseModel):
    scenario_type: str
    title: str
    description: str
    stance_spectrum: list[str]
    agent_archetypes: list[AgentArchetype]
    dynamics: str
    tick_count: int = Field(default=20, ge=1)

    @field_validator("stance_spectrum")
    @classmethod
    def validate_spectrum_length(cls, v: list[str]) -> list[str]:
        if len(v) != 5:
            raise ValueError("stance_spectrum must have exactly 5 labels")
        return v


# --- Agent Generator output ---

class Relationship(BaseModel):
    target: str
    type: str  # follows, distrusts, rivals, respects
    weight: float = Field(ge=0.0, le=1.0)


class Agent(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    bias: str
    initial_stance: float = Field(ge=0.0, le=1.0)
    behavioral_rules: list[str]
    relationships: list[Relationship] = Field(default_factory=list)


# --- Simulation Engine I/O ---

class TickAction(BaseModel):
    """Raw output from an agent's LLM call for one tick."""
    stance: float
    action: str
    emotion: str
    reasoning: str
    message: str
    influence_target: str | None = None

    @field_validator("stance")
    @classmethod
    def clamp_stance(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class TickEvent(BaseModel):
    """One agent's contribution to a tick, enriched with context."""
    agent_id: str
    stance: float
    previous_stance: float
    action: str
    emotion: str
    reasoning: str
    message: str
    influence_target: str | None = None


class TickRecord(BaseModel):
    """All events for a single tick."""
    tick: int
    events: list[TickEvent]
    aggregate_stance: float


# --- Run output ---

class BiggestShift(BaseModel):
    agent_id: str
    from_stance: float = Field(serialization_alias="from")
    to_stance: float = Field(serialization_alias="to")
    reason: str


class RunSummary(BaseModel):
    total_ticks: int
    final_aggregate_stance: float
    biggest_shift: BiggestShift
    consensus_reached: bool


class ScenarioInfo(BaseModel):
    input: str
    type: str
    title: str
    stance_spectrum: list[str]


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    persona: str
    bias: str
    initial_stance: float


class RunResult(BaseModel):
    model_config = {"populate_by_name": True}

    run_id: str
    scenario: ScenarioInfo
    agents: list[AgentInfo]
    ticks: list[TickRecord]
    summary: RunSummary


# --- API request ---

class SimulateRequest(BaseModel):
    prompt: str
    context: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/models.py tests/test_models.py
git commit -m "feat: add Pydantic models for all Pythia data structures"
```

---

### Task 3: Ollama Client

**Files:**
- Create: `src/pythia/llm.py`
- Create: `tests/test_llm.py`

Thin async HTTP wrapper for Ollama. Defines the `LLMClient` protocol so tests can use `FakeLLMClient`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_llm.py`:

```python
"""Tests for LLM client abstraction and Ollama client."""

import json
import pytest
import httpx
from pythia.llm import LLMClient, OllamaClient


class TestLLMClientProtocol:
    """Verify the FakeLLMClient satisfies the protocol."""

    @pytest.fixture
    def fake_client(self):
        from tests.conftest import FakeLLMClient
        return FakeLLMClient(responses=[{"result": "hello"}])

    async def test_fake_client_returns_canned_response(self, fake_client):
        result = await fake_client.generate("test prompt")
        assert result == {"result": "hello"}

    async def test_fake_client_records_calls(self, fake_client):
        await fake_client.generate("test prompt", system="sys")
        assert len(fake_client.calls) == 1
        assert fake_client.calls[0]["prompt"] == "test prompt"
        assert fake_client.calls[0]["system"] == "sys"

    async def test_fake_client_pops_responses_in_order(self, fake_client):
        fake_client.responses = [{"a": 1}, {"b": 2}]
        r1 = await fake_client.generate("p1")
        r2 = await fake_client.generate("p2")
        assert r1 == {"a": 1}
        assert r2 == {"b": 2}


class TestOllamaClient:
    """Test OllamaClient with mocked HTTP transport."""

    def _make_transport(self, response_body: dict) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"response": json.dumps(response_body)},
            )
        return httpx.MockTransport(handler)

    async def test_generate_parses_json_response(self):
        transport = self._make_transport({"stance": 0.5})
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        result = await client.generate("What is your stance?")
        assert result == {"stance": 0.5}

    async def test_generate_sends_correct_payload(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"response": '{"ok": true}'})

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        await client.generate("my prompt", system="my system")
        assert captured["body"]["model"] == "test-model"
        assert captured["body"]["prompt"] == "my prompt"
        assert captured["body"]["system"] == "my system"
        assert captured["body"]["format"] == "json"
        assert captured["body"]["stream"] is False

    async def test_generate_retries_on_malformed_json(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"response": "not valid json {{"})
            return httpx.Response(200, json={"response": '{"recovered": true}'})

        transport = httpx.MockTransport(handler)
        client = OllamaClient(
            base_url="http://fake:11434",
            model="test-model",
            http_client=httpx.AsyncClient(transport=transport),
        )
        result = await client.generate("prompt")
        assert result == {"recovered": True}
        assert call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_llm.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.llm'`

- [ ] **Step 3: Implement LLM client**

Create `src/pythia/llm.py`:

```python
"""LLM client abstraction and Ollama implementation."""

from __future__ import annotations

import json
from typing import Protocol

import httpx

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL


class LLMClient(Protocol):
    """Protocol for LLM backends. Implement generate() to swap providers."""

    async def generate(self, prompt: str, system: str | None = None) -> dict: ...


class OllamaClient:
    """Thin async HTTP wrapper for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url
        self.model = model
        self._http = http_client or httpx.AsyncClient(timeout=120.0)

    async def generate(self, prompt: str, system: str | None = None) -> dict:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }
        if system:
            payload["system"] = system

        response = await self._http.post(
            f"{self.base_url}/api/generate", json=payload
        )
        response.raise_for_status()
        raw = response.json()["response"]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # One retry with explicit JSON instruction
            payload["prompt"] = (
                "Your previous response was not valid JSON. "
                "Respond with ONLY valid JSON.\n\n" + prompt
            )
            response = await self._http.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            raw = response.json()["response"]
            return json.loads(raw)

    async def close(self):
        await self._http.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/llm.py tests/test_llm.py
git commit -m "feat: add Ollama LLM client with JSON mode and retry"
```

---

### Task 4: Scenario Analyzer

**Files:**
- Create: `src/pythia/analyzer.py`
- Create: `tests/test_analyzer.py`

Takes a user prompt + optional context, makes one LLM call, returns a validated `ScenarioBlueprint`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer.py`:

```python
"""Tests for the Scenario Analyzer."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.analyzer import analyze_scenario
from pythia.models import ScenarioBlueprint


MARKET_BLUEPRINT_RESPONSE = {
    "scenario_type": "market_event",
    "title": "Federal Reserve 50bps Rate Hike",
    "description": "Simulation of market reactions to rate increase",
    "stance_spectrum": ["very bearish", "bearish", "neutral", "bullish", "very bullish"],
    "agent_archetypes": [
        {"role": "retail_investor", "count": 2, "description": "Individual investors", "bias": "loss_aversion", "stance_range": [0.2, 0.4]},
        {"role": "institutional_investor", "count": 2, "description": "Fund managers", "bias": "anchoring", "stance_range": [0.5, 0.8]},
        {"role": "market_analyst", "count": 1, "description": "Analyst", "bias": "confirmation", "stance_range": [0.4, 0.6]},
    ],
    "dynamics": "Herd behavior likely among retail investors.",
    "tick_count": 20,
}

PERSONAL_BLUEPRINT_RESPONSE = {
    "scenario_type": "personal_decision",
    "title": "Buy vs Rent in Austin",
    "description": "Advisors and peers weigh in on housing decision",
    "stance_spectrum": ["strongly rent", "lean rent", "undecided", "lean buy", "strongly buy"],
    "agent_archetypes": [
        {"role": "financial_advisor", "count": 1, "description": "Conservative planner", "bias": "anchoring", "stance_range": [0.3, 0.5]},
        {"role": "homeowner_peer", "count": 2, "description": "Friends who bought", "bias": "confirmation", "stance_range": [0.6, 0.9]},
        {"role": "renter_peer", "count": 2, "description": "Friends who rent and invest", "bias": "status_quo", "stance_range": [0.1, 0.4]},
    ],
    "dynamics": "Peers share personal experiences. Advisor provides data-driven analysis.",
    "tick_count": 20,
}


class TestAnalyzeScenario:
    async def test_returns_valid_blueprint_for_market_event(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        result = await analyze_scenario("Fed raises rates 50bps", llm=llm)
        assert isinstance(result, ScenarioBlueprint)
        assert result.scenario_type == "market_event"
        assert len(result.agent_archetypes) == 3
        assert result.tick_count == 20

    async def test_returns_valid_blueprint_for_personal_decision(self):
        llm = FakeLLMClient(responses=[PERSONAL_BLUEPRINT_RESPONSE])
        result = await analyze_scenario("Should I buy or rent in Austin?", llm=llm)
        assert isinstance(result, ScenarioBlueprint)
        assert result.scenario_type == "personal_decision"
        assert result.stance_spectrum[0] == "strongly rent"

    async def test_passes_context_in_prompt(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates", context="Market is volatile", llm=llm)
        prompt_sent = llm.calls[0]["prompt"]
        assert "Market is volatile" in prompt_sent

    async def test_prompt_includes_user_input(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates 50bps", llm=llm)
        prompt_sent = llm.calls[0]["prompt"]
        assert "Fed raises rates 50bps" in prompt_sent

    async def test_system_prompt_describes_analyzer_role(self):
        llm = FakeLLMClient(responses=[MARKET_BLUEPRINT_RESPONSE])
        await analyze_scenario("Fed raises rates", llm=llm)
        system_sent = llm.calls[0]["system"]
        assert system_sent is not None
        assert "scenario" in system_sent.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_analyzer.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.analyzer'`

- [ ] **Step 3: Implement the analyzer**

Create `src/pythia/analyzer.py`:

```python
"""Scenario Analyzer — classifies user input into a simulation blueprint."""

from __future__ import annotations

import json

from pythia.llm import LLMClient
from pythia.models import ScenarioBlueprint

SYSTEM_PROMPT = """\
You are Pythia's Scenario Analyzer. Given a user's decision or question, you produce a simulation blueprint as JSON.

Your output MUST be a JSON object with these exact fields:
- scenario_type: string (e.g. "market_event", "personal_decision", "policy_test")
- title: string — short descriptive title
- description: string — one sentence describing the simulation
- stance_spectrum: array of exactly 5 strings — labels for positions from 0.0 to 1.0, appropriate to the scenario (e.g. ["very bearish", "bearish", "neutral", "bullish", "very bullish"] for markets, ["strongly oppose", "oppose", "neutral", "support", "strongly support"] for policy)
- agent_archetypes: array of objects, each with:
    - role: string
    - count: integer (1-3)
    - description: string
    - bias: string (a cognitive bias name)
    - stance_range: [low, high] — floats between 0.0 and 1.0, low < high
- dynamics: string — describes how agents should interact
- tick_count: integer (default 20)

Generate 3-5 archetypes with diverse stance_ranges that span the spectrum. Total agent count should be 5-10."""


async def analyze_scenario(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
) -> ScenarioBlueprint:
    """Analyze a user prompt and return a simulation blueprint."""
    user_prompt = f"User's decision/question: {prompt}"
    if context:
        user_prompt += f"\n\nAdditional context: {context}"

    raw = await llm.generate(prompt=user_prompt, system=SYSTEM_PROMPT)
    return ScenarioBlueprint.model_validate(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_analyzer.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/analyzer.py tests/test_analyzer.py
git commit -m "feat: add Scenario Analyzer — classifies input into simulation blueprint"
```

---

### Task 5: Agent Generator

**Files:**
- Create: `src/pythia/generator.py`
- Create: `tests/test_generator.py`

Two-pass generation: Pass 1 creates agents in parallel (one LLM call per archetype). Pass 2 assigns relationships (one LLM call seeing all agents).

- [ ] **Step 1: Write failing tests**

Create `tests/test_generator.py`:

```python
"""Tests for the Agent Generator."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.generator import generate_agents
from pythia.models import AgentArchetype, ScenarioBlueprint, Agent


def make_blueprint(**overrides) -> ScenarioBlueprint:
    defaults = {
        "scenario_type": "market_event",
        "title": "Test Scenario",
        "description": "A test",
        "stance_spectrum": ["vb", "b", "n", "bu", "vbu"],
        "agent_archetypes": [
            AgentArchetype(role="retail", count=1, description="Retail trader", bias="loss_aversion", stance_range=(0.2, 0.4)),
            AgentArchetype(role="institutional", count=1, description="Fund manager", bias="anchoring", stance_range=(0.6, 0.8)),
        ],
        "dynamics": "Test dynamics",
        "tick_count": 20,
    }
    defaults.update(overrides)
    return ScenarioBlueprint(**defaults)


# Pass 1 response: one agent per archetype (no relationships)
PASS1_RETAIL = {
    "agents": [
        {
            "id": "retail-rachel",
            "name": "Retail Rachel",
            "role": "retail",
            "persona": "34-year-old self-taught trader.",
            "bias": "loss_aversion",
            "initial_stance": 0.35,
            "behavioral_rules": ["Sells on bad news", "Follows social media"],
        }
    ]
}

PASS1_INSTITUTIONAL = {
    "agents": [
        {
            "id": "institutional-ivan",
            "name": "Institutional Ivan",
            "role": "institutional",
            "persona": "Veteran fund manager, 20 years experience.",
            "bias": "anchoring",
            "initial_stance": 0.7,
            "behavioral_rules": ["Holds through volatility", "Anchors to fundamentals"],
        }
    ]
}

# Pass 2 response: relationships for all agents
PASS2_RELATIONSHIPS = {
    "relationships": {
        "retail-rachel": [
            {"target": "institutional-ivan", "type": "distrusts", "weight": 0.7}
        ],
        "institutional-ivan": [
            {"target": "retail-rachel", "type": "respects", "weight": 0.3}
        ],
    }
}


class TestGenerateAgents:
    async def test_returns_correct_number_of_agents(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        assert len(agents) == 2

    async def test_agents_have_valid_structure(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        for agent in agents:
            assert isinstance(agent, Agent)
            assert agent.id
            assert agent.name
            assert agent.persona
            assert len(agent.behavioral_rules) > 0

    async def test_relationships_assigned_from_pass2(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        rachel = next(a for a in agents if a.id == "retail-rachel")
        assert len(rachel.relationships) == 1
        assert rachel.relationships[0].target == "institutional-ivan"

    async def test_pass1_calls_equal_archetype_count(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        await generate_agents(bp, llm=llm)
        # 2 archetypes = 2 pass1 calls + 1 pass2 call = 3 total
        assert len(llm.calls) == 3

    async def test_diversity_check_passes_with_spread_stances(self):
        llm = FakeLLMClient(responses=[PASS1_RETAIL, PASS1_INSTITUTIONAL, PASS2_RELATIONSHIPS])
        bp = make_blueprint()
        agents = await generate_agents(bp, llm=llm)
        stances = [a.initial_stance for a in agents]
        spread = max(stances) - min(stances)
        assert spread >= 0.3  # 0.7 - 0.35 = 0.35
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generator.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.generator'`

- [ ] **Step 3: Implement the generator**

Create `src/pythia/generator.py`:

```python
"""Agent Generator — creates fully realized agents from a scenario blueprint."""

from __future__ import annotations

import asyncio
import json

from pythia.llm import LLMClient
from pythia.models import Agent, AgentArchetype, Relationship, ScenarioBlueprint

PASS1_SYSTEM = """\
You are Pythia's Agent Generator. Given a scenario and an agent archetype, generate unique agents as JSON.

Your output MUST be a JSON object with an "agents" key containing an array. Each agent has:
- id: string — lowercase-hyphenated (e.g. "retail-rachel")
- name: string — a memorable character name
- role: string — matches the archetype role
- persona: string — 1-2 sentences describing personality, background, motivations (~50 words max)
- bias: string — the cognitive bias from the archetype
- initial_stance: float — between {stance_low} and {stance_high}
- behavioral_rules: array of 2-4 short strings describing how this agent behaves

Make each agent distinct and memorable. Give them human-like personalities."""

PASS2_SYSTEM = """\
You are assigning relationships between simulation agents. Given all agents, create a relationship graph.

Your output MUST be a JSON object with a "relationships" key. The value is an object where each key is an agent ID, and the value is an array of relationships:
- target: string — another agent's ID
- type: string — one of: "follows", "distrusts", "rivals", "respects"
- weight: float — 0.0 to 1.0 (how strong the relationship is)

Each agent should have 1-3 relationships. Relationships should make sense given their roles and personas."""


async def _generate_for_archetype(
    archetype: AgentArchetype,
    blueprint: ScenarioBlueprint,
    llm: LLMClient,
) -> list[Agent]:
    """Pass 1: Generate agents for one archetype."""
    system = PASS1_SYSTEM.format(
        stance_low=archetype.stance_range[0],
        stance_high=archetype.stance_range[1],
    )
    prompt = (
        f"Scenario: {blueprint.title} — {blueprint.description}\n"
        f"Dynamics: {blueprint.dynamics}\n"
        f"Stance spectrum: {json.dumps(blueprint.stance_spectrum)}\n\n"
        f"Archetype: {archetype.role}\n"
        f"Description: {archetype.description}\n"
        f"Bias: {archetype.bias}\n"
        f"Stance range: {archetype.stance_range[0]} to {archetype.stance_range[1]}\n"
        f"Count: {archetype.count}\n\n"
        f"Generate {archetype.count} agent(s)."
    )
    raw = await llm.generate(prompt=prompt, system=system)
    agents_data = raw.get("agents", [])
    return [
        Agent(
            id=a["id"],
            name=a["name"],
            role=a["role"],
            persona=a["persona"],
            bias=a["bias"],
            initial_stance=a["initial_stance"],
            behavioral_rules=a["behavioral_rules"],
            relationships=[],
        )
        for a in agents_data
    ]


async def _assign_relationships(
    agents: list[Agent],
    llm: LLMClient,
) -> list[Agent]:
    """Pass 2: Assign relationships given the full cast."""
    agent_summaries = [
        f"- {a.id} ({a.name}): {a.role}, bias={a.bias}, stance={a.initial_stance}, persona: {a.persona}"
        for a in agents
    ]
    prompt = "Agents in this simulation:\n" + "\n".join(agent_summaries)
    raw = await llm.generate(prompt=prompt, system=PASS2_SYSTEM)

    relationships_map = raw.get("relationships", {})
    agent_ids = {a.id for a in agents}

    updated = []
    for agent in agents:
        rels_data = relationships_map.get(agent.id, [])
        rels = [
            Relationship(target=r["target"], type=r["type"], weight=r["weight"])
            for r in rels_data
            if r.get("target") in agent_ids and r["target"] != agent.id
        ]
        updated.append(agent.model_copy(update={"relationships": rels}))
    return updated


def _check_diversity(agents: list[Agent], min_spread: float = 0.6) -> bool:
    """Check that initial stances span at least min_spread of the 0.0-1.0 range."""
    if len(agents) < 2:
        return True
    stances = [a.initial_stance for a in agents]
    return (max(stances) - min(stances)) >= min_spread


async def generate_agents(
    blueprint: ScenarioBlueprint,
    llm: LLMClient,
) -> list[Agent]:
    """Generate agents from a blueprint. Two-pass: create agents, then assign relationships."""
    # Pass 1: parallel generation per archetype
    tasks = [
        _generate_for_archetype(arch, blueprint, llm)
        for arch in blueprint.agent_archetypes
    ]
    results = await asyncio.gather(*tasks)
    agents = [agent for group in results for agent in group]

    # Diversity check: if stances are too clustered, regenerate the most extreme archetype
    if not _check_diversity(agents) and len(blueprint.agent_archetypes) > 1:
        stances = {a.id: a.initial_stance for a in agents}
        mean = sum(stances.values()) / len(stances)
        # Find the archetype whose agents are closest to the mean (most "average")
        archetype_dists = []
        for i, arch in enumerate(blueprint.agent_archetypes):
            arch_agents = [a for a in agents if a.role == arch.role]
            avg_dist = sum(abs(a.initial_stance - mean) for a in arch_agents) / max(len(arch_agents), 1)
            archetype_dists.append((i, avg_dist))
        archetype_dists.sort(key=lambda x: x[1])
        regen_idx = archetype_dists[0][0]
        regen_arch = blueprint.agent_archetypes[regen_idx]
        new_agents = await _generate_for_archetype(regen_arch, blueprint, llm)
        agents = [a for a in agents if a.role != regen_arch.role] + new_agents

    # Pass 2: assign relationships
    agents = await _assign_relationships(agents, llm)

    return agents
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generator.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/generator.py tests/test_generator.py
git commit -m "feat: add Agent Generator — two-pass agent creation with relationships"
```

---

### Task 6: Simulation Engine

**Files:**
- Create: `src/pythia/engine.py`
- Create: `tests/test_engine.py`

The core tick loop: perceive → reason → act, with AgentMemory and world state management.

- [ ] **Step 1: Write failing tests**

Create `tests/test_engine.py`:

```python
"""Tests for the Simulation Engine."""

import pytest
from tests.conftest import FakeLLMClient
from pythia.engine import SimulationEngine, AgentMemory
from pythia.models import Agent, Relationship, ScenarioBlueprint, AgentArchetype, TickRecord


def make_test_agents() -> list[Agent]:
    return [
        Agent(
            id="agent-a", name="Agent A", role="trader", persona="Cautious trader.",
            bias="loss_aversion", initial_stance=0.3,
            behavioral_rules=["Sells on bad news"],
            relationships=[Relationship(target="agent-b", type="follows", weight=0.5)],
        ),
        Agent(
            id="agent-b", name="Agent B", role="analyst", persona="Data-driven analyst.",
            bias="anchoring", initial_stance=0.7,
            behavioral_rules=["Holds to fundamentals"],
            relationships=[Relationship(target="agent-a", type="respects", weight=0.3)],
        ),
    ]


def make_test_blueprint() -> ScenarioBlueprint:
    return ScenarioBlueprint(
        scenario_type="market_event", title="Test", description="Test sim",
        stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        agent_archetypes=[
            AgentArchetype(role="trader", count=1, description="d", bias="loss_aversion", stance_range=(0.2, 0.4)),
        ],
        dynamics="Test dynamics", tick_count=3,
    )


TICK_RESPONSE_A = {
    "stance": 0.25,
    "action": "sell",
    "emotion": "anxious",
    "reasoning": "Bad signals from the market",
    "message": "I'm reducing my position.",
    "influence_target": "agent-b",
}

TICK_RESPONSE_B = {
    "stance": 0.68,
    "action": "hold",
    "emotion": "steady",
    "reasoning": "Fundamentals unchanged",
    "message": "Staying the course.",
    "influence_target": "agent-a",
}


class TestAgentMemory:
    def test_starts_empty(self):
        mem = AgentMemory("agent-a")
        assert mem.for_prompt() == []

    def test_records_and_retrieves(self):
        mem = AgentMemory("agent-a")
        mem.record({"tick": 1, "stance": 0.3})
        mem.record({"tick": 2, "stance": 0.25})
        assert len(mem.for_prompt()) == 2
        assert mem.for_prompt()[0]["tick"] == 1


class TestSimulationEngine:
    async def test_run_produces_correct_tick_count(self):
        # 3 ticks × 2 agents = 6 LLM calls
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        assert len(ticks) == 3

    async def test_each_tick_has_events_for_all_agents(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        for tick in ticks:
            assert isinstance(tick, TickRecord)
            assert len(tick.events) == 2

    async def test_tick_events_have_correct_agent_ids(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        agent_ids = {e.agent_id for e in ticks[0].events}
        assert agent_ids == {"agent-a", "agent-b"}

    async def test_aggregate_stance_is_average(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        # (0.25 + 0.68) / 2 = 0.465
        assert abs(ticks[0].aggregate_stance - 0.465) < 0.01

    async def test_previous_stance_tracks_correctly(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        ticks = await engine.run()
        # Tick 1: previous stance should be initial stance
        event_a_tick1 = next(e for e in ticks[0].events if e.agent_id == "agent-a")
        assert event_a_tick1.previous_stance == 0.3
        # Tick 2: previous stance should be tick 1's stance
        event_a_tick2 = next(e for e in ticks[1].events if e.agent_id == "agent-a")
        assert event_a_tick2.previous_stance == 0.25

    async def test_memory_grows_across_ticks(self):
        responses = [TICK_RESPONSE_A, TICK_RESPONSE_B] * 3
        llm = FakeLLMClient(responses=responses)
        engine = SimulationEngine(
            blueprint=make_test_blueprint(),
            agents=make_test_agents(),
            llm=llm,
        )
        await engine.run()
        # After 3 ticks, each agent's memory should have 3 entries
        assert len(engine.memories["agent-a"].for_prompt()) == 3
        assert len(engine.memories["agent-b"].for_prompt()) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.engine'`

- [ ] **Step 3: Implement the simulation engine**

Create `src/pythia/engine.py`:

```python
"""Simulation Engine — tick-by-tick opinion dynamics loop."""

from __future__ import annotations

import asyncio
import json

from pythia.llm import LLMClient
from pythia.models import (
    Agent,
    ScenarioBlueprint,
    TickAction,
    TickEvent,
    TickRecord,
)


class AgentMemory:
    """Stores an agent's full tick history for prompt inclusion."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.full_history: list[dict] = []

    def record(self, tick_event: dict) -> None:
        self.full_history.append(tick_event)

    def for_prompt(self) -> list[dict]:
        return self.full_history


AGENT_SYSTEM_TEMPLATE = """\
You are {name}, {persona}.

Your behavioral rules:
{rules}

Your cognitive bias: {bias}"""

AGENT_PROMPT_TEMPLATE = """\
Scenario: {title} — {description}
Dynamics: {dynamics}
Stance spectrum: {spectrum}

Current world state:
- Aggregate sentiment: {aggregate_stance} ({aggregate_label})
- Other agents:
{other_agents}

Messages directed at you:
{messages}

Your history:
{history}

---

Respond with ONLY this JSON (no other text):
{{"stance": <float 0.0-1.0>, "action": "<what you do>", "emotion": "<how you feel>", "reasoning": "<why in one sentence>", "message": "<what you say to others>", "influence_target": "<agent-id or null>"}}"""


def _stance_to_label(stance: float, spectrum: list[str]) -> str:
    """Map a 0.0-1.0 stance to one of 5 spectrum labels."""
    idx = min(int(stance * len(spectrum)), len(spectrum) - 1)
    return spectrum[idx]


def _format_rules(rules: list[str]) -> str:
    return "\n".join(f"- {r}" for r in rules)


def _format_history(memory: AgentMemory) -> str:
    entries = memory.for_prompt()
    if not entries:
        return "(no history yet — this is tick 1)"
    lines = []
    for e in entries:
        lines.append(
            f"Tick {e['tick']}: stance={e['stance']}, action={e['action']}, "
            f"emotion={e['emotion']}, reasoning=\"{e['reasoning']}\""
        )
    return "\n".join(lines)


def _format_other_agents(
    agent_id: str, current_stances: dict[str, dict], agents: list[Agent]
) -> str:
    lines = []
    for a in agents:
        if a.id == agent_id:
            continue
        state = current_stances.get(a.id, {})
        stance = state.get("stance", a.initial_stance)
        action = state.get("action", "none yet")
        lines.append(f"  - {a.name} ({a.role}): stance={stance:.2f}, last action={action}")
    return "\n".join(lines) if lines else "  (none)"


def _get_messages_for_agent(agent_id: str, recent_messages: list[dict]) -> str:
    msgs = [m for m in recent_messages if m.get("to") == agent_id]
    if not msgs:
        return "(no messages)"
    return "\n".join(
        f"  - {m['from_name']} (tick {m['tick']}): \"{m['message']}\""
        for m in msgs
    )


class SimulationEngine:
    """Runs the perceive → reason → act loop for all agents over N ticks."""

    def __init__(
        self,
        blueprint: ScenarioBlueprint,
        agents: list[Agent],
        llm: LLMClient,
    ):
        self.blueprint = blueprint
        self.agents = agents
        self.llm = llm
        self.memories: dict[str, AgentMemory] = {
            a.id: AgentMemory(a.id) for a in agents
        }
        self.current_stances: dict[str, dict] = {
            a.id: {"stance": a.initial_stance, "action": "none", "emotion": "neutral"}
            for a in agents
        }
        self.recent_messages: list[dict] = []
        self._agent_map: dict[str, Agent] = {a.id: a for a in agents}

    async def run(self) -> list[TickRecord]:
        """Run the full simulation and return all tick records."""
        tick_records: list[TickRecord] = []

        for tick_num in range(1, self.blueprint.tick_count + 1):
            tick_record = await self._run_tick(tick_num)
            tick_records.append(tick_record)

        return tick_records

    async def _run_tick(self, tick_num: int) -> TickRecord:
        """Run a single tick: all agents reason in parallel."""
        aggregate = self._compute_aggregate()

        tasks = [
            self._run_agent_tick(agent, tick_num, aggregate)
            for agent in self.agents
        ]
        events = await asyncio.gather(*tasks)

        # Update world state
        new_messages: list[dict] = []
        for event in events:
            self.current_stances[event.agent_id] = {
                "stance": event.stance,
                "action": event.action,
                "emotion": event.emotion,
            }
            self.memories[event.agent_id].record({
                "tick": tick_num,
                "stance": event.stance,
                "action": event.action,
                "emotion": event.emotion,
                "reasoning": event.reasoning,
            })
            if event.influence_target and event.influence_target in self._agent_map:
                new_messages.append({
                    "from": event.agent_id,
                    "from_name": self._agent_map[event.agent_id].name,
                    "to": event.influence_target,
                    "tick": tick_num,
                    "message": event.message,
                })

        self.recent_messages = new_messages

        new_aggregate = self._compute_aggregate()
        return TickRecord(
            tick=tick_num,
            events=events,
            aggregate_stance=round(new_aggregate, 4),
        )

    async def _run_agent_tick(
        self, agent: Agent, tick_num: int, aggregate: float
    ) -> TickEvent:
        """Build prompt for one agent, call LLM, validate and return TickEvent."""
        previous_stance = self.current_stances[agent.id]["stance"]

        system = AGENT_SYSTEM_TEMPLATE.format(
            name=agent.name,
            persona=agent.persona,
            rules=_format_rules(agent.behavioral_rules),
            bias=agent.bias,
        )

        prompt = AGENT_PROMPT_TEMPLATE.format(
            title=self.blueprint.title,
            description=self.blueprint.description,
            dynamics=self.blueprint.dynamics,
            spectrum=json.dumps(self.blueprint.stance_spectrum),
            aggregate_stance=f"{aggregate:.2f}",
            aggregate_label=_stance_to_label(aggregate, self.blueprint.stance_spectrum),
            other_agents=_format_other_agents(agent.id, self.current_stances, self.agents),
            messages=_get_messages_for_agent(agent.id, self.recent_messages),
            history=_format_history(self.memories[agent.id]),
        )

        raw = await self.llm.generate(prompt=prompt, system=system)
        action = TickAction.model_validate(raw)

        return TickEvent(
            agent_id=agent.id,
            stance=action.stance,
            previous_stance=previous_stance,
            action=action.action,
            emotion=action.emotion,
            reasoning=action.reasoning,
            message=action.message,
            influence_target=action.influence_target,
        )

    def _compute_aggregate(self) -> float:
        """Equal-weight average of all agent stances."""
        stances = [s["stance"] for s in self.current_stances.values()]
        return sum(stances) / len(stances)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/engine.py tests/test_engine.py
git commit -m "feat: add Simulation Engine — tick-by-tick opinion dynamics loop"
```

---

### Task 7: Run Orchestrator + CLI

**Files:**
- Create: `src/pythia/orchestrator.py`
- Create: `src/pythia/__main__.py`
- Create: `tests/test_orchestrator.py`

Wires Analyzer → Generator → Engine → Run JSON. Provides both a programmatic `run_simulation()` function and a CLI entry point.

- [ ] **Step 1: Write failing tests for the orchestrator**

Create `tests/test_orchestrator.py`:

```python
"""Tests for the simulation orchestrator."""

import json
import os
import pytest
from tests.conftest import FakeLLMClient
from pythia.orchestrator import run_simulation
from pythia.models import RunResult


# Canned LLM responses: 1 analyzer + 2 generator pass1 + 1 generator pass2 + (3 ticks × 2 agents)
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
        "initial_stance": 0.3, "behavioral_rules": ["Sells on dips"],
    }]
}

GEN_PASS1_ANALYST = {
    "agents": [{
        "id": "analyst-a", "name": "Analyst A", "role": "analyst",
        "persona": "An analyst.", "bias": "anchoring",
        "initial_stance": 0.7, "behavioral_rules": ["Holds steady"],
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


def make_all_responses() -> list[dict]:
    """1 analyzer + 2 gen pass1 + 1 gen pass2 + 3 ticks × 2 agents = 10 calls."""
    return [
        ANALYZER_RESPONSE,
        GEN_PASS1_TRADER, GEN_PASS1_ANALYST,
        GEN_PASS2,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
        TICK_TRADER, TICK_ANALYST,
    ]


class TestRunSimulation:
    async def test_produces_valid_run_result(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert isinstance(result, RunResult)
        assert result.scenario.title == "Test Event"
        assert len(result.agents) == 2
        assert len(result.ticks) == 3

    async def test_saves_run_json_to_disk(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        run_file = tmp_path / f"{result.run_id}.json"
        assert run_file.exists()
        data = json.loads(run_file.read_text())
        assert data["run_id"] == result.run_id

    async def test_summary_has_correct_tick_count(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert result.summary.total_ticks == 3

    async def test_biggest_shift_identified(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        result = await run_simulation(
            prompt="Test event",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        assert result.summary.biggest_shift.agent_id in ("trader-t", "analyst-a")

    async def test_context_passed_through(self, tmp_path):
        llm = FakeLLMClient(responses=make_all_responses())
        await run_simulation(
            prompt="Test event",
            context="Extra context here",
            llm=llm,
            runs_dir=str(tmp_path),
        )
        # First call is the analyzer — context should appear in prompt
        assert "Extra context here" in llm.calls[0]["prompt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_orchestrator.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.orchestrator'`

- [ ] **Step 3: Implement the orchestrator**

Create `src/pythia/orchestrator.py`:

```python
"""Orchestrator — wires Analyzer → Generator → Engine → RunResult."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pythia.analyzer import analyze_scenario
from pythia.config import RUNS_DIR
from pythia.engine import SimulationEngine
from pythia.generator import generate_agents
from pythia.llm import LLMClient
from pythia.models import (
    AgentInfo,
    BiggestShift,
    RunResult,
    RunSummary,
    ScenarioInfo,
)


def _generate_run_id() -> str:
    now = datetime.now(timezone.utc)
    return f"run_{now.strftime('%Y-%m-%d_%H%M%S')}"


def _compute_summary(result_partial: dict) -> RunSummary:
    """Compute run summary from ticks and agents."""
    ticks = result_partial["ticks"]
    agents = result_partial["agents"]

    total_ticks = len(ticks)
    final_aggregate = ticks[-1].aggregate_stance if ticks else 0.0

    # Find biggest shift: compare each agent's final stance to initial
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


async def run_simulation(
    prompt: str,
    llm: LLMClient,
    context: str | None = None,
    runs_dir: str = RUNS_DIR,
) -> RunResult:
    """Run the full simulation pipeline and return a RunResult."""
    # 1. Analyze scenario
    blueprint = await analyze_scenario(prompt, llm=llm, context=context)

    # 2. Generate agents
    agents = await generate_agents(blueprint, llm=llm)

    # 3. Run simulation
    engine = SimulationEngine(blueprint=blueprint, agents=agents, llm=llm)
    ticks = await engine.run()

    # 4. Build result
    run_id = _generate_run_id()

    agent_infos = [
        AgentInfo(
            id=a.id, name=a.name, role=a.role,
            persona=a.persona, bias=a.bias,
            initial_stance=a.initial_stance,
        )
        for a in agents
    ]

    partial = {"ticks": ticks, "agents": agents}
    summary = _compute_summary(partial)

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

    # 5. Save to disk
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    output_file = runs_path / f"{run_id}.json"
    output_file.write_text(result.model_dump_json(indent=2, by_alias=True))

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_orchestrator.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Implement the CLI entry point**

Create `src/pythia/__main__.py`:

```python
"""CLI entry point: python -m pythia"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL, RUNS_DIR


def _print_summary(result) -> None:
    """Print a human-readable summary to stdout."""
    s = result.scenario
    print(f"\n{'═' * 3} PYTHIA — {s.title} {'═' * 3}\n")
    print("Agents:")
    for agent in result.agents:
        # Find final stance from last tick
        final_stance = agent.initial_stance
        for tick in result.ticks:
            for event in tick.events:
                if event.agent_id == agent.id:
                    final_stance = event.stance
        direction = "▲" if final_stance > agent.initial_stance else "▼" if final_stance < agent.initial_stance else "─"
        print(f"  {agent.name:<22} [{agent.role}]  stance: {agent.initial_stance:.2f} → {final_stance:.2f}  {direction}")

    sm = result.summary
    first_agg = result.ticks[0].aggregate_stance if result.ticks else 0
    spectrum = s.stance_spectrum
    print(f"\nAggregate: {first_agg:.2f} → {sm.final_aggregate_stance:.2f}")
    print(f"Consensus: {'Yes' if sm.consensus_reached else 'No'}")
    bs = sm.biggest_shift
    delta = bs.to_stance - bs.from_stance
    print(f"Biggest shift: {bs.agent_id} ({delta:+.2f}) — {bs.reason}")
    print(f"\nFull run saved to data/runs/{result.run_id}.json")


async def _run(args: argparse.Namespace) -> None:
    from pythia.llm import OllamaClient
    from pythia.orchestrator import run_simulation

    llm = OllamaClient(base_url=args.ollama_url, model=args.model)
    try:
        result = await run_simulation(
            prompt=args.prompt,
            context=args.context,
            llm=llm,
            runs_dir=args.runs_dir,
        )
        _print_summary(result)
    finally:
        await llm.close()


def _serve(args: argparse.Namespace) -> None:
    import uvicorn
    from pythia.api import create_app

    app = create_app(ollama_url=args.ollama_url, model=args.model)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pythia", description="Pythia simulation engine")
    parser.add_argument("--ollama-url", default=OLLAMA_BASE_URL, help="Ollama API base URL")
    parser.add_argument("--model", default=OLLAMA_MODEL, help="Ollama model name")
    parser.add_argument("--runs-dir", default=RUNS_DIR, help="Output directory for run JSON files")

    subparsers = parser.add_subparsers(dest="command")

    # python -m pythia serve
    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")

    # python -m pythia "prompt" (positional, no subcommand needed)
    parser.add_argument("prompt", nargs="?", default=None, help="Decision or question to simulate")
    parser.add_argument("--context", default=None, help="Additional context paragraph")

    args = parser.parse_args()

    if args.command == "serve":
        _serve(args)
    elif args.prompt:
        asyncio.run(_run(args))
    else:
        parser.print_help()
        sys.exit(1)


main()
```

- [ ] **Step 6: Verify CLI help works**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && python -m pythia --help`

Expected: Prints help text with `run` and `serve` subcommands.

- [ ] **Step 7: Commit**

```bash
git add src/pythia/orchestrator.py src/pythia/__main__.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator and CLI entry point — python -m pythia run/serve"
```

---

### Task 8: FastAPI Server

**Files:**
- Create: `src/pythia/api.py`
- Create: `tests/test_api.py`

Three endpoints: `POST /api/simulate`, `GET /api/runs/{run_id}`, `GET /api/runs`. CORS enabled for Vite dev server.

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
"""Tests for the FastAPI server."""

import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from pythia.api import create_app
from pythia.models import (
    RunResult, RunSummary, ScenarioInfo, AgentInfo,
    BiggestShift, TickRecord, TickEvent,
)


def make_mock_result() -> RunResult:
    return RunResult(
        run_id="run_test_001",
        scenario=ScenarioInfo(
            input="Test prompt", type="market_event",
            title="Test", stance_spectrum=["vb", "b", "n", "bu", "vbu"],
        ),
        agents=[
            AgentInfo(id="a1", name="Agent 1", role="trader", persona="p", bias="b", initial_stance=0.3),
        ],
        ticks=[
            TickRecord(tick=1, events=[
                TickEvent(agent_id="a1", stance=0.35, previous_stance=0.3,
                          action="hold", emotion="calm", reasoning="r", message="m"),
            ], aggregate_stance=0.35),
        ],
        summary=RunSummary(
            total_ticks=1, final_aggregate_stance=0.35,
            biggest_shift=BiggestShift(agent_id="a1", from_stance=0.3, to_stance=0.35, reason="r"),
            consensus_reached=True,
        ),
    )


class TestSimulateEndpoint:
    @pytest.fixture
    def app(self):
        return create_app(ollama_url="http://fake:11434", model="test")

    async def test_simulate_returns_run_result(self, app):
        mock_result = make_mock_result()
        with patch("pythia.api.run_simulation", new_callable=AsyncMock, return_value=mock_result):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/simulate", json={"prompt": "Test prompt"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run_test_001"
        assert data["scenario"]["title"] == "Test"

    async def test_simulate_requires_prompt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/simulate", json={})
        assert resp.status_code == 422


class TestRunsEndpoints:
    async def test_get_runs_returns_list(self, tmp_path):
        # Write a fake run file
        run_data = make_mock_result().model_dump()
        (tmp_path / "run_test_001.json").write_text(json.dumps(run_data))

        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run_test_001"

    async def test_get_run_by_id(self, tmp_path):
        run_data = make_mock_result().model_dump()
        (tmp_path / "run_test_001.json").write_text(json.dumps(run_data))

        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/run_test_001")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == "run_test_001"

    async def test_get_nonexistent_run_returns_404(self, tmp_path):
        app = create_app(ollama_url="http://fake:11434", model="test", runs_dir=str(tmp_path))
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/runs/nonexistent")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pythia.api'`

- [ ] **Step 3: Implement the API server**

Create `src/pythia/api.py`:

```python
"""FastAPI server for Pythia."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pythia.config import OLLAMA_BASE_URL, OLLAMA_MODEL, RUNS_DIR
from pythia.llm import OllamaClient
from pythia.models import SimulateRequest, RunResult
from pythia.orchestrator import run_simulation


def create_app(
    ollama_url: str = OLLAMA_BASE_URL,
    model: str = OLLAMA_MODEL,
    runs_dir: str = RUNS_DIR,
) -> FastAPI:
    app = FastAPI(title="Pythia", description="Opinion dynamics simulation engine")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    llm = OllamaClient(base_url=ollama_url, model=model)

    @app.post("/api/simulate")
    async def simulate(request: SimulateRequest) -> dict:
        result = await run_simulation(
            prompt=request.prompt,
            context=request.context,
            llm=llm,
            runs_dir=runs_dir,
        )
        return result.model_dump()

    @app.get("/api/runs")
    async def list_runs() -> list[dict]:
        runs_path = Path(runs_dir)
        if not runs_path.exists():
            return []
        runs = []
        for f in sorted(runs_path.glob("run_*.json"), reverse=True):
            data = json.loads(f.read_text())
            runs.append({
                "run_id": data.get("run_id", f.stem),
                "title": data.get("scenario", {}).get("title", "Unknown"),
                "type": data.get("scenario", {}).get("type", "unknown"),
            })
        return runs

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run_file = Path(runs_dir) / f"{run_id}.json"
        if not run_file.exists():
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return json.loads(run_file.read_text())

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/api.py tests/test_api.py
git commit -m "feat: add FastAPI server — simulate, list runs, get run endpoints"
```

---

### Task 9: UI Input Bar + Wiring

**Files:**
- Create: `src/ui/src/components/InputBar.jsx`
- Modify: `src/ui/src/App.jsx`
- Modify: `src/ui/src/simulation/useSimulation.js`
- Modify: `src/ui/src/simulation/scenarios.js`

Adds a text input to the React app. When submitted, it calls the API and feeds the result into the existing simulation components. The app still works with the mock scenario when no API is available.

- [ ] **Step 1: Create InputBar component**

Create `src/ui/src/components/InputBar.jsx`:

```jsx
import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function InputBar({ onSimulationResult, isLoading, setIsLoading }) {
  const [prompt, setPrompt] = useState('')
  const [context, setContext] = useState('')
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const resp = await fetch(`${API_BASE}/api/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          context: context.trim() || undefined,
        }),
      })

      if (!resp.ok) {
        throw new Error(`Simulation failed: ${resp.status}`)
      }

      const result = await resp.json()
      onSimulationResult(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{
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
        style={{
          flex: 1,
          background: '#0D0D0B',
          border: '1px solid #2a2a25',
          borderRadius: '4px',
          padding: '8px 12px',
          color: '#d4c9a8',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
        }}
      />
      <input
        type="text"
        value={context}
        onChange={e => setContext(e.target.value)}
        placeholder="Optional context..."
        disabled={isLoading}
        style={{
          width: '200px',
          background: '#0D0D0B',
          border: '1px solid #2a2a25',
          borderRadius: '4px',
          padding: '8px 12px',
          color: '#d4c9a8',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
        }}
      />
      <button
        type="submit"
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
      {error && (
        <span style={{ color: '#C08878', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </span>
      )}
    </form>
  )
}
```

- [ ] **Step 2: Add adapter function to scenarios.js**

Modify `src/ui/src/simulation/scenarios.js` — add a function that maps API run result to the frontend's scenario format:

```javascript
// Add to the end of the existing file:

const AGENT_COLORS = [
  { color: '#B8907A', glow: 'rgba(184,144,122,0.32)' },
  { color: '#7A9BA8', glow: 'rgba(122,155,168,0.32)' },
  { color: '#A09B7A', glow: 'rgba(160,155,122,0.32)' },
  { color: '#C08878', glow: 'rgba(192,136,120,0.32)' },
  { color: '#8A9B8A', glow: 'rgba(138,155,138,0.32)' },
  { color: '#9B8AA0', glow: 'rgba(155,138,160,0.32)' },
  { color: '#A0907A', glow: 'rgba(160,144,122,0.32)' },
  { color: '#7AA09B', glow: 'rgba(122,160,155,0.32)' },
  { color: '#8A7A9B', glow: 'rgba(138,122,155,0.32)' },
  { color: '#9BA07A', glow: 'rgba(155,160,122,0.32)' },
]

export function scenarioFromRunResult(result) {
  const protagonists = result.agents.map((agent, i) => ({
    id: agent.id,
    name: agent.name,
    trait: agent.bias,
    color: AGENT_COLORS[i % AGENT_COLORS.length].color,
    glow: AGENT_COLORS[i % AGENT_COLORS.length].glow,
  }))

  const amendments = result.agents.map(agent => [
    'Recalibrating',
    `${agent.bias} parameters...`,
  ])

  return {
    name: result.scenario.title,
    protagonists,
    amendments,
    ticks: result.ticks,
    agents: result.agents,
  }
}
```

- [ ] **Step 3: Update useSimulation to support API-driven replay**

Modify `src/ui/src/simulation/useSimulation.js` — add a `useApiSimulation` hook that replays API tick data through the existing reducer:

```javascript
// Add to the end of the existing file:

export function useApiSimulation(scenario) {
  const [state, dispatch] = useReducer(simReducer, scenario.protagonists, makeInitialState)
  const timerRef = useRef(null)
  const tickDataRef = useRef(scenario.ticks || [])

  // Spawn stagger on mount
  useEffect(() => {
    const timeouts = scenario.protagonists.map((_, i) =>
      setTimeout(() => {
        const agentData = scenario.agents?.[i]
        const initialConf = agentData ? agentData.initial_stance * 100 : 28 + Math.random() * 28
        dispatch({ type: 'SPAWN', idx: i, conf: initialConf })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, scenario.protagonists.length])

  // Tick interval — replay API data
  useEffect(() => {
    const ticks = tickDataRef.current
    timerRef.current = setInterval(() => {
      dispatch({ type: 'TICK' })
    }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen])

  // Update confidence from API tick data
  useEffect(() => {
    const tickData = tickDataRef.current[state.tick - 1]
    if (!tickData || !tickData.events) return
    tickData.events.forEach(event => {
      const idx = scenario.protagonists.findIndex(p => p.id === event.agent_id)
      if (idx >= 0) {
        dispatch({ type: 'SPAWN', idx, conf: event.stance * 100 })
      }
    })
  }, [state.tick])

  // Temple entry at tick 9
  useEffect(() => {
    if (state.tick !== 9 || state.templeIdx !== null) return
    const active = state.protoStates
      .map((ps, i) => (ps.spawned && !ps.inTemple ? i : -1))
      .filter(i => i >= 0)
    if (active.length === 0) return
    const idx = active[Math.floor(Math.random() * active.length)]
    dispatch({ type: 'SEND_TO_TEMPLE', idx })
  }, [state.tick])

  // Temple exit at tick 16
  useEffect(() => {
    if (state.tick !== 16 || state.templeIdx === null) return
    dispatch({ type: 'RETURN_FROM_TEMPLE' })
  }, [state.tick])

  // Clear returning flag
  useEffect(() => {
    const returningIdx = state.protoStates.findIndex(ps => ps.returning)
    if (returningIdx === -1) return
    const t = setTimeout(() => {
      dispatch({ type: 'MARK_NOT_RETURNING', idx: returningIdx })
    }, 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  // End of run
  useEffect(() => {
    if (state.tick <= TICKS_PER_RUN) return
    dispatch({ type: 'END_RUN' })
  }, [state.tick])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    dispatch({ type: 'RESET', protagonists: scenario.protagonists })
  }, [scenario.protagonists])

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / TICKS_PER_RUN) * 100,
    crowdStateIndex: state.crowdStateIndex,
    crowdStateName: CROWD_STATES[state.crowdStateIndex],
    templeIdx: state.templeIdx,
    protoStates: state.protoStates,
    accuracyHistory: state.accuracyHistory,
    amendments: scenario.amendments,
    restart,
  }
}
```

- [ ] **Step 4: Update App.jsx to support both mock and API modes**

Replace `src/ui/src/App.jsx`:

```jsx
import { useState } from 'react'
import { useSimulation, useApiSimulation } from './simulation/useSimulation'
import { getScenario, scenarioFromRunResult } from './simulation/scenarios'
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

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <InputBar
        onSimulationResult={setRunResult}
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
      ) : runResult ? (
        <ApiSimulation runResult={runResult} />
      ) : (
        <MockSimulation />
      )}
    </div>
  )
}
```

- [ ] **Step 5: Run existing UI tests to verify no regressions**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npx vitest run`

Expected: All 18 existing tests PASS. (The new components use hooks that require browser context — manual testing covers those.)

- [ ] **Step 6: Commit**

```bash
git add src/ui/src/components/InputBar.jsx src/ui/src/App.jsx src/ui/src/simulation/useSimulation.js src/ui/src/simulation/scenarios.js
git commit -m "feat: add UI input bar and API-driven simulation replay"
```

---

### Task 10: End-to-End Verification

**Files:** None — verification only.

- [ ] **Step 1: Run all Python tests**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && python -m pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 2: Run all UI tests**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npx vitest run`

Expected: All tests PASS.

- [ ] **Step 3: Verify Ollama is available**

Run: `ollama list`

If Ollama is not installed, install it and pull a model:
```bash
# Install Ollama (if not present)
brew install ollama
# Pull a model
ollama pull llama3.1:8b
```

- [ ] **Step 4: Test CLI end-to-end with Ollama**

Run: `cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia && python -m pythia "Fed raises rates 50bps"`

Expected: Prints agent summary, saves JSON to `data/runs/`. Verify the JSON file exists and has the expected structure (agents, ticks, summary).

- [ ] **Step 5: Test API server end-to-end**

Run: `python -m pythia serve` (in one terminal)

In another terminal:
```bash
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Should I buy or rent in Austin?"}'
```

Expected: Returns full run JSON with agents appropriate to a personal decision.

- [ ] **Step 6: Test UI end-to-end**

With the API server running, start the UI:
```bash
cd /Users/utkarshbajaj/Documents/05-Code-Projects/Pythia/src/ui && npm run dev
```

Open `http://localhost:5173`, type a prompt in the input bar, click "Consult the Oracle." Verify the simulation visualization updates with real agent data.

- [ ] **Step 7: Final commit and update PROGRESS.md**

```bash
# Update PROGRESS.md with Phase 1 completion status
git add docs/PROGRESS.md
git commit -m "docs: update PROGRESS.md — Phase 1 simulation backbone complete"
```
