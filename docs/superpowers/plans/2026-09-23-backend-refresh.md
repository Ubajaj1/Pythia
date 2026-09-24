# Backend Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make simulation output reliable and observable (no silent parse failures, per-run token and cost accounting, a verdict that can't contradict its numbers), refresh Claude model support, and stream the data the new chart-recorder UI needs (agent camps, influence events, run quality).

**Architecture:** Changes stay inside existing modules and follow their patterns: the engine gains a retry-and-count wrapper around the tick LLM call; a new `usage` module collects token counts through a `ContextVar` that each client writes to; the orchestrator's stream adds `influence` events and a `quality` block on `done`; the Anthropic client handles thinking blocks, refusals, and server-side fallbacks; `llm.py` gains per-role model configuration.

**Tech Stack:** Python 3.11, FastAPI, httpx (raw HTTP clients kept as-is), pydantic v2, pytest + pytest-asyncio; Vitest for the one frontend demo fix.

**Spec:** Track 4 decisions in this conversation, summarized in "Global Constraints" (no separate spec file). Related: `docs/superpowers/specs/2026-09-23-ui-redesign-design.md` § "Data needed from the backend".

## Global Constraints

- Branch: `feat/backend-refresh` from `origin/main`. If the Kitaru branch has merged first, `parse_model_spec` already exists in `src/pythia/llm.py`; reuse it rather than redefining.
- Claude model IDs are used exactly as written, without date suffixes: `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`. Defaults when `ANTHROPIC_API_KEY` is set: main role `claude-opus-5`, tick role `claude-haiku-4-5` (the user may override; confirm with them before merging, since Opus 5 costs more than today's Haiku default).
- Claude pricing per 1M tokens (input / output): Opus 5 $5 / $25, Sonnet 5 $2 / $10, Haiku 4.5 $1 / $5.
- Requests to `claude-opus-5` send the server-side fallback beta: header `anthropic-beta: server-side-fallback-2026-07-01` and body `"fallbacks": "default"`.
- Every Anthropic response is checked for `stop_reason == "refusal"` before reading content.
- Keep the existing raw-HTTP Anthropic client (the project deliberately uses httpx; migrating to the SDK is out of scope).
- The existing test suite stays green after every task.
- New SSE event types must be additive; the current UI ignores unknown event types (`App.jsx` if/else chain).
- **Found 2026-09-24:** Groq has retired `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` (404), so Pythia's Groq path is broken. In Task 3, change `GROQ_MODEL` / `GROQ_FAST_MODEL` defaults in `config.py` to `openai/gpt-oss-120b` / `openai/gpt-oss-20b`, add both to `_GROQ_RPM_BY_MODEL`, and note Groq's free tier is 8k tokens/min per model (about 15 min per 5×8 run).

---

### Task 1: Housekeeping

**Files:**
- Delete: `src/agents/`, `src/feedback/`, `src/ingestion/`, `src/simulation/`, `src/skills/` (empty, untracked)

- [ ] **Step 1: Sync and branch**

```bash
git fetch origin
git checkout main && git pull --ff-only origin main
git checkout -b feat/backend-refresh
```

- [ ] **Step 2: Remove the empty directories**

```bash
rmdir src/agents src/feedback src/ingestion src/simulation src/skills
```

Expected: no error (`rmdir` refuses non-empty directories, which is the safety check).

- [ ] **Step 3: Baseline test run**

Run: `python3 -m pytest -q`
Expected: all pass (307 at the time of planning). Record the number.

No commit (untracked directories don't appear in git).

---

### Task 2: Anthropic client for current models

**Files:**
- Modify: `src/pythia/anthropic_client.py` (constants, payload/headers, success branch)
- Modify: `src/pythia/config.py:14`
- Test: `tests/test_anthropic_client.py`

**Interfaces:**
- Produces: `AnthropicRefusal(AnthropicError)` exception; `_response_text(body: dict) -> str`; `_MAX_TOKENS = 16000`; `FALLBACK_MODELS = {"claude-opus-5"}`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_anthropic_client.py`)

```python
from pythia.anthropic_client import AnthropicRefusal, _response_text


def _mock_body(body: dict, seen: list | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(200, json=body)
    return httpx.MockTransport(handler)


class TestCurrentModels:
    def test_response_text_skips_thinking_blocks(self):
        body = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"a": 1}'}]}
        assert _response_text(body) == '{"a": 1}'

    def test_response_text_joins_multiple_text_blocks(self):
        body = {"content": [{"type": "text", "text": '{"a":'}, {"type": "text", "text": " 1}"}]}
        assert _response_text(body) == '{"a": 1}'

    async def test_thinking_first_response_parses(self):
        body = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"stance": 0.4}'}], "stop_reason": "end_turn"}
        client = _make_client(_mock_body(body))
        assert await client.generate("p") == {"stance": 0.4}

    async def test_refusal_raises(self):
        body = {"content": [], "stop_reason": "refusal", "stop_details": {"type": "refusal", "category": "cyber"}}
        client = _make_client(_mock_body(body))
        with pytest.raises(AnthropicRefusal):
            await client.generate("p")

    async def test_opus_5_sends_fallbacks(self):
        seen = []
        body = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"}
        client = AnthropicClient(api_key="k", model="claude-opus-5", http_client=httpx.AsyncClient(transport=_mock_body(body, seen)), rpm=0)
        await client.generate("p")
        req = seen[0]
        assert req.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
        assert json.loads(req.content)["fallbacks"] == "default"

    async def test_haiku_does_not_send_fallbacks(self):
        seen = []
        body = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn"}
        client = AnthropicClient(api_key="k", model="claude-haiku-4-5", http_client=httpx.AsyncClient(transport=_mock_body(body, seen)), rpm=0)
        await client.generate("p")
        assert "anthropic-beta" not in seen[0].headers
        assert "fallbacks" not in json.loads(seen[0].content)
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_anthropic_client.py -v -k CurrentModels`
Expected: FAIL with `ImportError: cannot import name 'AnthropicRefusal'`.

- [ ] **Step 3: Implement**

In `src/pythia/anthropic_client.py`:

1. Replace `_MAX_TOKENS = 4096` with `_MAX_TOKENS = 16000`, and add below the constants:

```python
# Models that get Anthropic's server-side refusal fallback by default.
FALLBACK_MODELS = {"claude-opus-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
```

2. Add after `class AnthropicError`:

```python
class AnthropicRefusal(AnthropicError):
    """The model declined the request (stop_reason == "refusal")."""


def _response_text(body: dict) -> str:
    """Concatenate text blocks, skipping thinking and other block types."""
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
```

3. In `generate`, after building `payload` and `headers`, add:

```python
        if self.model in FALLBACK_MODELS:
            payload["fallbacks"] = "default"
            headers["anthropic-beta"] = _FALLBACK_BETA
```

4. In the success branch, replace:

```python
            body = response.json()
            raw = body["content"][0]["text"]
            stop_reason = body.get("stop_reason")
```

with:

```python
            body = response.json()
            stop_reason = body.get("stop_reason")
            if stop_reason == "refusal":
                category = (body.get("stop_details") or {}).get("category")
                raise AnthropicRefusal(f"Model {self.model} declined the request (category={category}).")
            raw = _response_text(body)
```

5. Update the class docstring example model to `"claude-haiku-4-5"`.

In `src/pythia/config.py`, change the default:

```python
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
ANTHROPIC_TICK_MODEL = os.getenv("ANTHROPIC_TICK_MODEL", "claude-haiku-4-5")
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_anthropic_client.py -v`
Expected: all pass, including the pre-existing ones (their mock bodies have a single text block).

- [ ] **Step 5: Commit**

```bash
git add src/pythia/anthropic_client.py src/pythia/config.py tests/test_anthropic_client.py
git commit -m "fix(anthropic): handle thinking blocks, refusals, and server-side fallbacks"
```

---

### Task 3: Per-role model configuration

**Files:**
- Modify: `src/pythia/llm.py` (add `parse_model_spec`, `build_role_clients`)
- Modify: `src/pythia/api.py:65-80` (replace fast-LLM block)
- Modify: `src/pythia/orchestrator.py` (`run_simulation` gains `fast_llm`)
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `build_llm_client(provider, ollama_url, model)`, config `ANTHROPIC_TICK_MODEL`, `GROQ_FAST_MODEL`
- Produces:
  - `parse_model_spec(spec: str) -> tuple[str, str]`
  - `build_role_clients(provider: str | None = None, ollama_url: str | None = None, model: str | None = None) -> tuple[LLMClient, LLMClient | None]` returning `(main, tick)`; `tick` is `None` when the main client should also run ticks
  - Env vars: `PYTHIA_MAIN_MODEL`, `PYTHIA_TICK_MODEL` (each `provider:model`)
  - `run_simulation(..., fast_llm: LLMClient | None = None)`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_llm.py`)

```python
import pytest

from pythia import llm as llm_mod


def test_parse_model_spec():
    assert llm_mod.parse_model_spec("anthropic:claude-haiku-4-5") == ("anthropic", "claude-haiku-4-5")
    with pytest.raises(ValueError):
        llm_mod.parse_model_spec("claude-haiku-4-5")


def test_role_env_specs_win(monkeypatch):
    built = []
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: built.append((provider, model)) or (provider, model))
    monkeypatch.setenv("PYTHIA_MAIN_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setenv("PYTHIA_TICK_MODEL", "groq:llama-3.1-8b-instant")
    main, tick = llm_mod.build_role_clients()
    assert main == ("openai", "gpt-4o-mini")
    assert tick == ("groq", "llama-3.1-8b-instant")


def test_anthropic_default_gets_haiku_tick(monkeypatch):
    monkeypatch.delenv("PYTHIA_MAIN_MODEL", raising=False)
    monkeypatch.delenv("PYTHIA_TICK_MODEL", raising=False)
    monkeypatch.setattr("pythia.config.ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: (provider, model))
    main, tick = llm_mod.build_role_clients()
    assert main == (None, None)
    assert tick == ("anthropic", "claude-haiku-4-5")


def test_explicit_model_disables_tick_split(monkeypatch):
    monkeypatch.delenv("PYTHIA_TICK_MODEL", raising=False)
    monkeypatch.delenv("PYTHIA_MAIN_MODEL", raising=False)
    monkeypatch.setattr(llm_mod, "build_llm_client", lambda provider=None, ollama_url=None, model=None: (provider, model))
    main, tick = llm_mod.build_role_clients(model="gpt-4o")
    assert tick is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_llm.py -v -k "spec or role or tick"`
Expected: FAIL with `AttributeError: module 'pythia.llm' has no attribute 'parse_model_spec'`.

- [ ] **Step 3: Implement in `src/pythia/llm.py`** (append at end of file)

```python
def parse_model_spec(spec: str) -> tuple[str, str]:
    """Split "provider:model" into its parts."""
    provider, sep, model = spec.partition(":")
    if not sep or not provider or not model:
        raise ValueError(f"Model spec must look like 'provider:model', got {spec!r}")
    return provider, model


def build_role_clients(
    provider: str | None = None,
    ollama_url: str | None = None,
    model: str | None = None,
) -> tuple[LLMClient, LLMClient | None]:
    """Return (main, tick) clients.

    main runs analysis, generation, and summaries; tick runs per-agent turns.
    Priority: PYTHIA_MAIN_MODEL / PYTHIA_TICK_MODEL env specs > provider defaults.
    tick is None when one client should do everything (explicit --model, Ollama, OpenAI).
    """
    import os
    from pythia import config

    main_spec = os.getenv("PYTHIA_MAIN_MODEL")
    tick_spec = os.getenv("PYTHIA_TICK_MODEL")

    if main_spec:
        p, m = parse_model_spec(main_spec)
        main = build_llm_client(provider=p, ollama_url=ollama_url, model=m)
    else:
        main = build_llm_client(provider=provider, ollama_url=ollama_url, model=model)

    if tick_spec:
        p, m = parse_model_spec(tick_spec)
        return main, build_llm_client(provider=p, ollama_url=ollama_url, model=m)
    if model or main_spec:
        return main, None

    effective = provider or (
        "anthropic" if config.ANTHROPIC_API_KEY else
        "groq" if config.GROQ_API_KEY else
        "openai" if config.OPENAI_API_KEY else
        "ollama"
    )
    if effective == "anthropic":
        return main, build_llm_client(provider="anthropic", ollama_url=ollama_url, model=config.ANTHROPIC_TICK_MODEL)
    if effective == "groq":
        return main, build_llm_client(provider="groq", ollama_url=ollama_url, model=config.GROQ_FAST_MODEL)
    return main, None
```

If Kitaru's `src/pythia/recording.py` defines its own `parse_model_spec`, replace that definition with `from pythia.llm import parse_model_spec`.

- [ ] **Step 4: Use it in `create_app`**

In `src/pythia/api.py`, replace from `llm = build_llm_client(provider=provider, ollama_url=ollama_url, model=model)` through the end of the `fast_llm = (...)` expression with:

```python
    llm, fast_llm = build_role_clients(provider=provider, ollama_url=ollama_url, model=model)
```

Update the import line to `from pythia.llm import build_role_clients` and remove the now-unused config imports (`ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GROQ_FAST_MODEL`, `OPENAI_API_KEY`) if nothing else in the file uses them (`grep -n` to check).

In `src/pythia/orchestrator.py`, add `fast_llm: LLMClient | None = None` as the last parameter of `run_simulation`, and change its engine construction to `llm=fast_llm or llm`. In `api.py`'s `/api/simulate` handler pass `fast_llm=fast_llm`.

- [ ] **Step 5: Run the suite**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/pythia/llm.py src/pythia/api.py src/pythia/orchestrator.py tests/test_llm.py
git commit -m "feat(llm): per-role model configuration with Claude defaults"
```

---

### Task 4: Token and cost tracking

**Files:**
- Create: `src/pythia/usage.py`
- Modify: `src/pythia/anthropic_client.py`, `src/pythia/openai_compat_client.py`, `src/pythia/llm.py` (Ollama) — one `record_usage` call each
- Test: `tests/test_usage.py`

**Interfaces:**
- Produces:
  - `PRICES_PER_MTOK: dict[str, tuple[float, float]]`
  - `@dataclass RunUsage(calls: int = 0, input_tokens: int = 0, output_tokens: int = 0, cost_usd: float | None = 0.0, by_model: dict[str, dict] = field(default_factory=dict))` with `to_dict() -> dict`
  - `record_usage(model: str, input_tokens: int, output_tokens: int) -> None` (no-op when no scope is active)
  - `start_usage() -> tuple[RunUsage, Token]` and `stop_usage(token) -> None`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for per-run token and cost accounting."""

import asyncio

from pythia.usage import RunUsage, record_usage, start_usage, stop_usage


def test_no_scope_is_noop():
    record_usage("claude-haiku-4-5", 10, 10)


def test_records_tokens_and_cost():
    usage, token = start_usage()
    try:
        record_usage("claude-haiku-4-5", 1_000_000, 1_000_000)
        record_usage("claude-haiku-4-5", 0, 0)
    finally:
        stop_usage(token)
    assert usage.calls == 2
    assert usage.input_tokens == 1_000_000 and usage.output_tokens == 1_000_000
    assert abs(usage.cost_usd - 6.0) < 1e-9
    assert usage.by_model["claude-haiku-4-5"]["calls"] == 2


def test_unknown_model_makes_cost_unknown():
    usage, token = start_usage()
    try:
        record_usage("mystery-model", 10, 10)
    finally:
        stop_usage(token)
    assert usage.cost_usd is None


async def test_child_tasks_share_the_scope():
    usage, token = start_usage()
    try:
        async def call():
            record_usage("claude-haiku-4-5", 1, 1)
        await asyncio.gather(call(), call(), call())
    finally:
        stop_usage(token)
    assert usage.calls == 3


def test_to_dict_rounds_cost():
    u = RunUsage(calls=1, input_tokens=5, output_tokens=5, cost_usd=0.123456789)
    assert u.to_dict()["cost_usd"] == 0.123457
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_usage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pythia.usage'`.

- [ ] **Step 3: Implement `src/pythia/usage.py`**

```python
"""Per-run token and cost accounting.

Clients call record_usage() after each response. A run opens a scope with
start_usage(); asyncio tasks created inside the run inherit the ContextVar,
so concurrent agent calls all land in the same RunUsage.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

# USD per 1M tokens (input, output). Claude prices from the Claude API reference
# (2026-09). Verify the non-Claude rows against provider pricing pages before release.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gpt-4o-mini": (0.15, 0.60),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
}


@dataclass
class RunUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0
    by_model: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": None if self.cost_usd is None else round(self.cost_usd, 6),
            "by_model": self.by_model,
        }


_current: ContextVar[RunUsage | None] = ContextVar("pythia_run_usage", default=None)


def start_usage() -> tuple[RunUsage, Token]:
    usage = RunUsage()
    return usage, _current.set(usage)


def stop_usage(token: Token) -> None:
    try:
        _current.reset(token)
    except ValueError:
        # An async generator can be finalized in a different context than it started in.
        _current.set(None)


def record_usage(model: str, input_tokens: int, output_tokens: int) -> None:
    usage = _current.get()
    if usage is None:
        return
    usage.calls += 1
    usage.input_tokens += input_tokens
    usage.output_tokens += output_tokens
    m = usage.by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    m["calls"] += 1
    m["input_tokens"] += input_tokens
    m["output_tokens"] += output_tokens
    price = PRICES_PER_MTOK.get(model)
    if price is None or usage.cost_usd is None:
        usage.cost_usd = None
    else:
        usage.cost_usd += (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_usage.py -v`
Expected: 5 passed.

- [ ] **Step 5: Record usage in each client**

`src/pythia/anthropic_client.py`, right after `stop_reason = body.get("stop_reason")` in the success branch:

```python
            u = body.get("usage") or {}
            record_usage(self.model, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)))
```

`src/pythia/openai_compat_client.py`, replace `raw = response.json()["choices"][0]["message"]["content"]` with:

```python
            data = response.json()
            raw = data["choices"][0]["message"]["content"]
            u = data.get("usage") or {}
            record_usage(self.model, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))
```

`src/pythia/llm.py` (`OllamaClient.generate`), replace the first `raw = response.json()["response"]` with:

```python
        data = response.json()
        raw = data["response"]
        record_usage(self.model, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0)))
```

Add `from pythia.usage import record_usage` to each of the three modules.

- [ ] **Step 6: Add a client-level test** (append to `tests/test_anthropic_client.py`)

```python
from pythia.usage import start_usage, stop_usage


async def test_anthropic_records_usage():
    body = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 20}}
    client = AnthropicClient(api_key="k", model="claude-haiku-4-5", http_client=httpx.AsyncClient(transport=_mock_body(body)), rpm=0)
    usage, token = start_usage()
    try:
        await client.generate("p")
    finally:
        stop_usage(token)
    assert usage.input_tokens == 100 and usage.output_tokens == 20 and usage.calls == 1
```

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/pythia/usage.py src/pythia/anthropic_client.py src/pythia/openai_compat_client.py src/pythia/llm.py tests/test_usage.py tests/test_anthropic_client.py
git commit -m "feat(usage): per-run token and cost accounting across providers"
```

---

### Task 5: Reliable agent-tick output

**Files:**
- Modify: `src/pythia/engine.py` (`SimulationEngine.__init__`, `_run_agent_tick`, new `_generate_action`)
- Test: `tests/test_engine.py`

**Interfaces:**
- Produces: `SimulationEngine.parse_retries: int`, `SimulationEngine.parse_failures: int`, module constants `REQUIRED_TICK_KEYS = ("stance", "reasoning")` and `REPAIR_PREFIX`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_engine.py`)

```python
class TestTickReliability:
    def _engine(self, responses):
        bp = make_test_blueprint().model_copy(update={"tick_count": 1})
        return SimulationEngine(blueprint=bp, agents=make_test_agents(), llm=FakeLLMClient(responses=responses))

    async def test_empty_response_is_retried_once(self):
        engine = self._engine([{}, TICK_RESPONSE_A, TICK_RESPONSE_B])
        ticks = await engine.run()
        a = next(e for e in ticks[0].events if e.agent_id == "agent-a")
        assert a.reasoning == TICK_RESPONSE_A["reasoning"]
        assert engine.parse_retries == 1
        assert engine.parse_failures == 0

    async def test_two_bad_responses_fall_back_and_count(self):
        engine = self._engine([{}, {"stance": "not-a-number"}, TICK_RESPONSE_B])
        ticks = await engine.run()
        a = next(e for e in ticks[0].events if e.agent_id == "agent-a")
        assert a.reasoning == "Failed to parse response"
        assert a.stance == 0.3
        assert engine.parse_failures == 1

    async def test_retry_prompt_asks_for_json(self):
        llm = FakeLLMClient(responses=[{}, TICK_RESPONSE_A, TICK_RESPONSE_B])
        bp = make_test_blueprint().model_copy(update={"tick_count": 1})
        engine = SimulationEngine(blueprint=bp, agents=make_test_agents(), llm=llm)
        await engine.run()
        assert llm.calls[1]["prompt"].startswith("Your previous reply was not valid")
```

Note: `FakeLLMClient.generate` never suspends, so agent-a's call and retry complete before agent-b's first call, which makes the response order deterministic.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_engine.py -v -k Reliability`
Expected: FAIL with `AttributeError: 'SimulationEngine' object has no attribute 'parse_retries'` (or the reasoning assertion).

- [ ] **Step 3: Implement**

At module level in `src/pythia/engine.py` (after the logger):

```python
# A tick reply must carry at least these keys; anything less counts as a parse failure.
REQUIRED_TICK_KEYS = ("stance", "reasoning")
REPAIR_PREFIX = (
    "Your previous reply was not valid. Reply with ONLY the JSON object described below, "
    "including every field.\n\n"
)
```

In `SimulationEngine.__init__`, after `self.influence_graph = InfluenceGraph()`:

```python
        self.parse_retries = 0
        self.parse_failures = 0
```

Add the method to `SimulationEngine`:

```python
    async def _generate_action(
        self, agent: Agent, tick_num: int, prompt: str, system: str, previous_stance: float,
    ) -> TickAction:
        """Call the LLM for one agent turn; retry once on an unusable reply, then fall back."""
        for attempt in range(2):
            try:
                raw = await self.llm.generate(prompt=prompt if attempt == 0 else REPAIR_PREFIX + prompt, system=system)
                if isinstance(raw, dict) and all(k in raw for k in REQUIRED_TICK_KEYS):
                    return TickAction.model_validate(raw)
                problem = f"missing required keys, got {raw!r}"
            except ValueError as exc:  # json.JSONDecodeError and pydantic.ValidationError are ValueErrors
                problem = str(exc)
            if attempt == 0:
                self.parse_retries += 1
                logger.warning("Agent tick unusable, retrying agent=%s tick=%d problem=%s", agent.name, tick_num, problem)
        self.parse_failures += 1
        logger.warning("Agent tick failed twice agent=%s tick=%d — using fallback", agent.name, tick_num)
        return TickAction(stance=previous_stance, action="none", emotion="confused",
                          reasoning="Failed to parse response", message="")
```

In `_run_agent_tick`, replace the block from `raw = await self.llm.generate(prompt=prompt, system=system)` through the end of its `except` fallback with:

```python
        action = await self._generate_action(agent, tick_num, prompt, system, previous_stance)
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_engine.py -v`
Expected: all pass. Then `python3 -m pytest -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/pythia/engine.py tests/test_engine.py
git commit -m "fix(engine): retry unusable agent replies once and count failures"
```

---

### Task 6: Stream data for the chart-recorder UI

**Files:**
- Modify: `src/pythia/models.py` (`Agent`, `AgentInfo`, new `RunQuality`, `RunResultWithInsights`)
- Modify: `src/pythia/generator.py` (`_generate_for_archetype`)
- Modify: `src/pythia/orchestrator.py` (`stream_simulation`, `run_simulation`, new helpers)
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `SimulationEngine.parse_retries/parse_failures` (Task 5), `start_usage/stop_usage/RunUsage.to_dict` (Task 4)
- Produces:
  - `Agent.archetype: str | None = None`; `AgentInfo.camp: str | None = None`
  - `class RunQuality(BaseModel)`: `parse_retries: int = 0`, `parse_failures: int = 0`, `usage: dict = {}`
  - `RunResultWithInsights.quality: RunQuality | None = None`
  - SSE event `{"type": "influence", "data": {"tick": int, "edges": [InfluenceEdge JSON]}}` after every `tick` event
  - `influence_payload(graph: InfluenceGraph, tick: int) -> dict`; `agent_infos(agents: list[Agent]) -> list[AgentInfo]`

- [ ] **Step 1: Write the failing test** (append to `tests/test_orchestrator.py`)

```python
from pythia.orchestrator import stream_simulation


async def test_stream_emits_camps_influence_and_quality(tmp_path):
    llm = FakeLLMClient(responses=make_all_responses())
    events = [e async for e in stream_simulation("q", llm=llm, runs_dir=str(tmp_path))]
    types = [e["type"] for e in events]

    scenario = next(e for e in events if e["type"] == "scenario")
    assert {a["camp"] for a in scenario["data"]["agents"]} == {"trader", "analyst"}

    tick_idx = [i for i, t in enumerate(types) if t == "tick"]
    assert len(tick_idx) == 3
    for i in tick_idx:
        assert types[i + 1] == "influence"
        assert events[i + 1]["data"]["tick"] == events[i]["data"]["tick"]
    first_influence = events[tick_idx[0] + 1]["data"]["edges"]
    assert any(e["edge_type"] == "message" for e in first_influence)

    done = events[-1]
    assert done["type"] == "done"
    assert done["data"]["quality"]["parse_failures"] == 0
    assert "usage" in done["data"]["quality"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_orchestrator.py -v -k stream_emits`
Expected: FAIL with `KeyError: 'camp'`.

- [ ] **Step 3: Models**

In `src/pythia/models.py`: add to `Agent` (after `relationships`):

```python
    # The analyzer archetype this agent was generated from; the UI groups agents into camps by it.
    archetype: str | None = None
```

Add to `AgentInfo` (after `initial_stance`):

```python
    camp: str | None = None
```

Add before `RunResultWithInsights`:

```python
class RunQuality(BaseModel):
    """How cleanly a run executed: retried/failed agent turns and token spend."""
    parse_retries: int = 0
    parse_failures: int = 0
    usage: dict = Field(default_factory=dict)
```

Add to `RunResultWithInsights` (after `methodology`):

```python
    quality: RunQuality | None = None
```

- [ ] **Step 4: Generator**

In `src/pythia/generator.py` `_generate_for_archetype`, add `archetype=archetype.role,` to the `Agent(...)` constructor call. In `_assign_relationships`, `model_copy` preserves it; no change there.

- [ ] **Step 5: Orchestrator**

In `src/pythia/orchestrator.py` add helpers after `_maybe_ground`:

```python
def agent_infos(agents: list[Agent]) -> list[AgentInfo]:
    return [
        AgentInfo(
            id=a.id, name=a.name, role=a.role, persona=a.persona,
            bias=a.bias, bias_strength=a.bias_strength,
            initial_stance=a.initial_stance, camp=a.archetype or a.role,
        )
        for a in agents
    ]


def influence_payload(graph: InfluenceGraph, tick: int) -> dict:
    return {"tick": tick, "edges": [e.model_dump(mode="json") for e in graph.edges if e.tick == tick]}
```

Imports: add `Agent`, `InfluenceGraph`, `RunQuality` to the `pythia.models` import; add `from pythia.usage import start_usage, stop_usage`.

In `stream_simulation`:
1. First statement of the body: `usage, usage_token = start_usage()`, and wrap the rest of the body in `try:` / `finally: stop_usage(usage_token)`.
2. Replace the inline `agent_infos = [...]` list with `infos = agent_infos(agents)` and use `infos` in the `scenario` payload.
3. After `yield {"type": "tick", ...}` add `yield {"type": "influence", "data": influence_payload(engine.influence_graph, tick_record.tick)}`.
4. In the `RunResultWithInsights(...)` construction add:

```python
        quality=RunQuality(
            parse_retries=engine.parse_retries,
            parse_failures=engine.parse_failures,
            usage=usage.to_dict(),
        ),
```

In `run_simulation`, open the same usage scope around the body and pass the same `quality=` argument.

Check `build_run_result` in `src/pythia/summary.py`: if it builds `AgentInfo` itself, pass `camp=a.archetype or a.role` there too (`grep -n "AgentInfo(" src/pythia/*.py` and update every constructor that has an `Agent` in hand).

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest -q`
Expected: all pass, including the new stream test.

- [ ] **Step 7: Commit**

```bash
git add src/pythia/models.py src/pythia/generator.py src/pythia/orchestrator.py src/pythia/summary.py tests/test_orchestrator.py
git commit -m "feat(stream): agent camps, per-tick influence events, run quality"
```

---

### Task 7: Verdict consistent with the numbers

**Files:**
- Modify: `src/pythia/models.py` (`DecisionSummary`)
- Modify: `src/pythia/decision.py` (`_build_decision_prompt`, `generate_decision_summary`)
- Modify: `src/ui/src/simulation/demo.js` (verdict text)
- Test: `tests/test_decision.py`, `src/ui/src/simulation/demo.test.js`

**Interfaces:**
- Produces: `DecisionSummary.verdict_label: str | None = None` (the stance-spectrum label for the final aggregate, computed deterministically); `export function demoVerdict(finalAgg)` in `demo.js`

- [ ] **Step 1: Write the failing Python tests** (append to `tests/test_decision.py`)

First read the top of `tests/test_decision.py` to reuse its existing run-result and graph helpers (names differ per file; use whatever builds a `RunResult` with `stance_spectrum=["vb", "b", "n", "bu", "vbu"]` and a final aggregate). The tests:

```python
async def test_verdict_label_follows_final_aggregate(make_result_with_final):
    result, graph = make_result_with_final(0.28)
    llm = FakeLLMClient(responses=[{"verdict": "Buy everything now"}])
    summary = await generate_decision_summary(result, graph, llm)
    assert summary.verdict_label == "b"


async def test_prompt_pins_the_direction(make_result_with_final):
    result, graph = make_result_with_final(0.28)
    llm = FakeLLMClient(responses=[{}])
    await generate_decision_summary(result, graph, llm)
    assert "must describe a b outcome" in llm.calls[0]["prompt"]
```

If the file has no such helper, add this fixture at the top of the test file:

```python
import pytest
from pythia.models import (
    AgentInfo, BiggestShift, InfluenceGraph, RunResult, RunSummary, ScenarioInfo, TickEvent, TickRecord,
)


@pytest.fixture
def make_result_with_final():
    def _make(final: float):
        result = RunResult(
            run_id="run-x",
            scenario=ScenarioInfo(input="q", type="t", title="T", stance_spectrum=["vb", "b", "n", "bu", "vbu"]),
            agents=[AgentInfo(id="a", name="A", role="r", persona="p", bias="anchoring", initial_stance=0.5)],
            ticks=[TickRecord(tick=1, aggregate_stance=final, events=[TickEvent(
                agent_id="a", stance=final, previous_stance=0.5, action="sell",
                emotion="calm", reasoning="r", message="m")])],
            summary=RunSummary(total_ticks=1, final_aggregate_stance=final,
                               biggest_shift=BiggestShift(agent_id="a", from_stance=0.5, to_stance=final, reason="r"),
                               consensus_reached=False),
        )
        return result, InfluenceGraph()
    return _make
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_decision.py -v -k "verdict_label or pins"`
Expected: FAIL (`verdict_label` is not a field / prompt text missing).

- [ ] **Step 3: Implement**

`src/pythia/models.py`, in `DecisionSummary` after `verdict_stance`:

```python
    # Stance-spectrum label for the final aggregate, computed from the numbers (never by the LLM).
    verdict_label: str | None = None
```

`src/pythia/decision.py`: import `from pythia.engine import _stance_to_label`. In `_build_decision_prompt`, after the "COMPUTED CONFIDENCE" lines, add:

```python
    label = _stance_to_label(result.summary.final_aggregate_stance, result.scenario.stance_spectrum)
    lines += [
        f"FINAL AGGREGATE: {result.summary.final_aggregate_stance:.2f} = \"{label}\".",
        f"Your verdict must describe a {label} outcome. Do not describe the panel as leaning the other way.",
        "",
    ]
```

In `generate_decision_summary`, add to the `DecisionSummary(...)` call:

```python
        verdict_label=_stance_to_label(result.summary.final_aggregate_stance, result.scenario.stance_spectrum),
```

- [ ] **Step 4: Run Python tests**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Write the failing demo test**

Create `src/ui/src/simulation/demo.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { demoVerdict } from './demo.js'

describe('demoVerdict', () => {
  it('describes selling when the aggregate is below neutral', () => {
    expect(demoVerdict(0.28)).toMatch(/selling/)
    expect(demoVerdict(0.28)).not.toMatch(/accumulat/)
  })
  it('describes accumulating when the aggregate is above neutral', () => {
    expect(demoVerdict(0.62)).toMatch(/accumulat/)
  })
  it('describes a split room near neutral', () => {
    expect(demoVerdict(0.5)).toMatch(/split/)
  })
})
```

Run: `cd src/ui && npx vitest run src/simulation/demo.test.js`
Expected: FAIL (`demoVerdict` is not exported).

- [ ] **Step 6: Implement in `demo.js`**

Add above `buildDoneResult`:

```js
export function demoVerdict(finalAgg) {
  if (finalAgg < 0.45) {
    return 'The panel leans toward selling on this Fed rate decision. Retail and momentum voices moved to the exit while institutional money held near neutral, so the move has support but is not a crowded trade.'
  }
  if (finalAgg > 0.55) {
    return 'The panel leans cautiously toward accumulating on this Fed rate decision. Institutional and momentum voices converged above neutral while retail held back, so the move has support but is not a crowded trade.'
  }
  return 'The panel is split on this Fed rate decision. Neither camp moved the room far from neutral, so there is no clear trade yet.'
}
```

In `buildDoneResult`, replace the hard-coded `verdict:` template string with `verdict: demoVerdict(finalAgg),`.

- [ ] **Step 7: Run frontend tests**

Run: `cd src/ui && npx vitest run`
Expected: all pass (39 existing + 3 new).

- [ ] **Step 8: Commit**

```bash
git add src/pythia/models.py src/pythia/decision.py tests/test_decision.py src/ui/src/simulation/demo.js src/ui/src/simulation/demo.test.js
git commit -m "fix(verdict): pin verdict direction to the final aggregate; fix demo contradiction"
```

---

### Task 8: Verify end to end

- [ ] **Step 1: Full suites**

```bash
python3 -m pytest -q
cd src/ui && npx vitest run
```

Expected: everything passes.

- [ ] **Step 2: Live smoke run (costs a few cents; ask the user first)**

With the user's approval, run one small simulation against a real provider:

```bash
python3 -m pythia serve &
curl -sN -X POST localhost:8000/api/simulate/stream -H 'content-type: application/json' \
  -d '{"prompt":"Should we raise a Series A or stay bootstrapped?","agent_count":3,"tick_count":5}' \
  | grep -o '"type": "[a-z]*"' | sort | uniq -c
```

Expected: counts include `tick` 5, `influence` 5, one each of `thinking`, `blueprint`, `scenario`, `done`. Then check the saved run in `data/runs/` has `quality.usage.cost_usd` set and `decision_summary.verdict_label` present. Stop the server.

- [ ] **Step 3: Update README "Tech stack" and env documentation**

Add `PYTHIA_MAIN_MODEL`, `PYTHIA_TICK_MODEL`, and `ANTHROPIC_TICK_MODEL` to the README's configuration notes with the `provider:model` format, and commit:

```bash
git add README.md
git commit -m "docs: document per-role model configuration"
```
