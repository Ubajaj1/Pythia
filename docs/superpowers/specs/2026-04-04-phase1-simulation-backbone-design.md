# Phase 1 — Simulation Backbone Design Spec

> Date: 2026-04-04
> Status: Draft
> Scope: Backend simulation engine producing structured tick events from natural language input

---

## Overview

Phase 1 delivers a Python backend that takes a short user prompt (1-2 sentences) with optional context, generates a cast of LLM-powered agents, runs a tick-by-tick opinion dynamics simulation, and outputs structured JSON events.

**Three demo scenarios:**
1. **Market sentiment** (Tier 1) — "Fed raises rates 50bps"
2. **Personal decision** (new category) — "Should I buy or rent in Austin?"
3. **Policy stress-testing** (Tier 2) — "City bans short-term rentals"

**Key decisions made during brainstorming:**
- Custom engine, no framework (no OASIS/CAMEL-AI dependency)
- Local models via Ollama for all LLM calls (swappable later)
- Structured JSON agent output (stance + action + reasoning + message)
- Full agent memory (all ticks), with abstraction layer for future compression
- Dual input: CLI and HTTP API (FastAPI), both supported in Phase 1
- UI input bar added to React app to submit prompts and display results

---

## Architecture

```
Input Sources:
    ├── CLI:   python -m pythia "Fed raises rates 50bps"
    └── HTTP:  POST /api/simulate {"prompt": "...", "context": "..."}
                 ▲
                 │ React UI (input bar → fetch → display)
                 │
         ┌───────┴────────┐
         │   FastAPI       │  Thin API layer — one endpoint to start
         │   Server        │  python -m pythia serve
         └───────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐ ┌──────────┐ ┌──────────┐
│Scenario│ │  Agent   │ │Simulation│
│Analyzer│→│Generator │→│  Engine  │→ Run JSON
└────────┘ └──────────┘ └──────────┘
```

**LLM Provider:** Ollama HTTP API (`http://localhost:11434`). No SDK dependency. Model configurable (default: Llama 3.1 8B). Swappable to Claude/OpenAI later by changing the HTTP call layer.

---

## Component 1: Scenario Analyzer

**Responsibility:** Classify the user's input and produce a simulation blueprint.

**Input:** `{ "prompt": "Fed raises rates 50bps", "context": "optional paragraph" }`

**Output (one LLM call):**

```json
{
  "scenario_type": "market_event",
  "title": "Federal Reserve 50bps Rate Hike",
  "description": "Simulation of market participant reactions to a significant interest rate increase",
  "stance_spectrum": ["very bearish", "bearish", "neutral", "bullish", "very bullish"],
  "agent_archetypes": [
    {
      "role": "retail_investor",
      "count": 2,
      "description": "Individual investors with moderate portfolios",
      "bias": "loss_aversion",
      "stance_range": [0.2, 0.4]
    },
    {
      "role": "institutional_investor",
      "count": 2,
      "description": "Fund managers with large positions",
      "bias": "anchoring",
      "stance_range": [0.5, 0.8]
    },
    {
      "role": "market_analyst",
      "count": 1,
      "description": "Independent analyst providing commentary",
      "bias": "confirmation",
      "stance_range": [0.4, 0.6]
    }
  ],
  "dynamics": "Agents react to the event and to each other's positions. Herd behavior likely among retail investors.",
  "tick_count": 20
}
```

**Key details:**
- `stance_spectrum` is always a labeled 5-point spectrum mapping to 0.0–1.0. Labels change per scenario type (bearish↔bullish, oppose↔support, against↔for).
- `agent_archetypes` includes `stance_range` per archetype to ensure diversity of initial positions.
- `dynamics` is a plain-English description the Simulation Engine can include in agent prompts to set the tone of interactions.
- The analyzer produces a blueprint, not agents. Clean separation of concerns.

**File:** `src/pythia/analyzer.py`

---

## Component 2: Agent Generator

**Responsibility:** Take the blueprint and generate fully realized agents.

**Input:** Scenario blueprint from the Analyzer.

**Two-pass generation:**

1. **Pass 1 — Create agents (one LLM call per archetype, parallelized):** Generate each agent's persona, bias, initial stance, and behavioral rules. No relationships yet — agents don't know about each other.
2. **Pass 2 — Assign relationships (one LLM call, sequential):** Given the full list of generated agents, a single LLM call assigns the relationship graph — who influences whom, trust/distrust dynamics.

**Agent output (after both passes):**

```json
{
  "id": "retail-rachel",
  "name": "Retail Rachel",
  "role": "retail_investor",
  "persona": "34-year-old self-taught trader who started during the 2024 meme stock era. Heavy in tech stocks. Checks her portfolio 12 times a day.",
  "bias": "loss_aversion",
  "initial_stance": 0.35,
  "relationships": [
    {"target": "institutional-ivan", "type": "distrusts", "weight": 0.7},
    {"target": "early-adopter-elias", "type": "follows", "weight": 0.5}
  ],
  "behavioral_rules": [
    "Sells quickly when sentiment turns negative",
    "Heavily influenced by social media chatter",
    "Anchors to her buy price, not fundamentals"
  ]
}
```

**Field purposes:**
- `persona` — Rich enough to give the LLM a character during ticks, short enough to fit in every tick prompt (~50 words).
- `bias` — Named cognitive bias shaping reasoning. This is what the Temple of Learning eventually amends (Phase 2).
- `initial_stance` — Starting position on 0.0–1.0 spectrum. Must fall within the archetype's `stance_range`.
- `relationships` — Directed influence graph. Determines who sees whose messages. Types: `follows`, `distrusts`, `rivals`, `respects`.
- `behavioral_rules` — Plain English rules the agent follows. The "scrolls" the Temple rewrites later.

**Agent count:** 5–10 total per simulation.

**Diversity guarantee:** Post-generation, check that initial stances span at least 60% of the 0.0–1.0 range. If too clustered, regenerate the outlier archetype.

**File:** `src/pythia/generator.py`

---

## Component 3: Simulation Engine

**Responsibility:** Run the tick-by-tick simulation loop.

### World State

```json
{
  "tick": 7,
  "scenario": {"title": "...", "description": "...", "dynamics": "..."},
  "stance_spectrum": ["very bearish", "...", "very bullish"],
  "aggregate_stance": 0.42,
  "agents": {
    "retail-rachel": {"stance": 0.3, "emotion": "anxious", "last_action": "sell"},
    "institutional-ivan": {"stance": 0.65, "emotion": "confident", "last_action": "hold"}
  },
  "recent_messages": [
    {"from": "institutional-ivan", "to": "retail-rachel", "tick": 6, "message": "Retail is overreacting. Fundamentals haven't changed."}
  ]
}
```

### Per-Tick Flow

```
For each tick (1 to N):
    │
    ├── For each agent (parallelized):
    │     ├── Build prompt:
    │     │     - Agent persona + behavioral rules (fixed)
    │     │     - Current world state snapshot
    │     │     - Messages directed at this agent (from relationships)
    │     │     - Full history of this agent's own actions (memory)
    │     │
    │     ├── Call Ollama → structured JSON:
    │     │     {
    │     │       "stance": 0.25,
    │     │       "action": "sell",
    │     │       "emotion": "panicking",
    │     │       "reasoning": "Everyone's dumping, I can't be the last one holding",
    │     │       "message": "I'm out. This is 2024 all over again.",
    │     │       "influence_target": "early-adopter-elias"
    │     │     }
    │     │
    │     └── Validate output (schema check, clamp stance to 0.0–1.0)
    │
    ├── Update world state:
    │     - Write each agent's new stance, emotion, action
    │     - Recalculate aggregate_stance (equal-weight average of all agent stances)
    │     - Route messages: add to recent_messages for the influence_target
    │
    └── Emit tick event
```

### Agent Prompt Structure (per tick)

```
System: You are {name}, {persona}.

Your behavioral rules:
{behavioral_rules as bullet list}

Your cognitive bias: {bias}

---

Scenario: {scenario title and description}
Dynamics: {dynamics}
Stance spectrum: {stance_spectrum labels}

Current world state:
- Aggregate sentiment: {aggregate_stance} ({mapped label})
- Other agents: {each agent's current stance and last action}

Messages directed at you:
{recent messages where target == this agent}

Your history:
{full list of own previous tick actions}

---

Respond with ONLY this JSON:
{"stance": 0.0-1.0, "action": "...", "emotion": "...", "reasoning": "...", "message": "...", "influence_target": "agent-id or null"}
```

### Memory

```python
class AgentMemory:
    def __init__(self, agent_id):
        self.full_history = []

    def record(self, tick_event):
        self.full_history.append(tick_event)

    def for_prompt(self):
        # Full history for now.
        # Swap to summarization later if context pressure grows.
        return self.full_history
```

Full history is stored and sent in prompts. At 20 ticks with ~100-150 tokens per tick entry, total memory is ~2,000-3,000 tokens — fits within 8K context models.

### Parallelism

- **Within a tick:** All agents reason in parallel (they read the same world state snapshot). Uses `asyncio.gather()` for concurrent Ollama HTTP calls.
- **Across ticks:** Sequential. Tick N+1 cannot start until all tick N agents have responded and world state is updated.

**File:** `src/pythia/engine.py`

---

## Component 4: Ollama Client

**Responsibility:** Thin HTTP wrapper for Ollama API calls.

```python
class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="llama3.1:8b"):
        self.base_url = base_url
        self.model = model

    async def generate(self, prompt, system=None, format="json"):
        # POST to /api/generate
        # Returns parsed JSON response
        # Retries once on malformed JSON
        ...
```

**Key details:**
- Uses `format: "json"` to force Ollama's JSON mode for reliable structured output.
- One retry on malformed JSON (re-prompt with "Your previous response was not valid JSON. Respond with ONLY valid JSON.").
- Configurable model and base URL. Swap to any Ollama-hosted model by changing the config.
- Async for parallel tick calls.
- Future: add an `LLMClient` protocol/interface so we can swap in Claude/OpenAI by implementing the same `generate()` method.

**File:** `src/pythia/llm.py`

---

## Component 5: Output Format

### Run JSON (written to file)

```json
{
  "run_id": "run_2026-04-04_001",
  "scenario": {
    "input": "Fed raises rates 50bps",
    "type": "market_event",
    "title": "Federal Reserve 50bps Rate Hike",
    "stance_spectrum": ["very bearish", "bearish", "neutral", "bullish", "very bullish"]
  },
  "agents": [
    {
      "id": "retail-rachel",
      "name": "Retail Rachel",
      "role": "retail_investor",
      "persona": "...",
      "bias": "loss_aversion",
      "initial_stance": 0.35
    }
  ],
  "ticks": [
    {
      "tick": 1,
      "events": [
        {
          "agent_id": "retail-rachel",
          "stance": 0.30,
          "previous_stance": 0.35,
          "action": "sell",
          "emotion": "anxious",
          "reasoning": "Rate hikes always crush my tech positions",
          "message": "Getting out before this gets worse.",
          "influence_target": "early-adopter-elias"
        }
      ],
      "aggregate_stance": 0.42
    }
  ],
  "summary": {
    "total_ticks": 20,
    "final_aggregate_stance": 0.58,
    "biggest_shift": {
      "agent_id": "retail-rachel",
      "from": 0.35,
      "to": 0.72,
      "reason": "Influenced by institutional confidence after tick 12"
    },
    "consensus_reached": false
  }
}
```

**Output location:** `data/runs/{run_id}.json`

### CLI stdout summary

```
═══ PYTHIA — Federal Reserve 50bps Rate Hike ═══

Agents:
  Retail Rachel      [retail_investor]  stance: 0.35 → 0.72  ▲
  Institutional Ivan [institutional]    stance: 0.65 → 0.61  ▼
  Early Adopter Elias[early_adopter]    stance: 0.50 → 0.68  ▲
  ...

Aggregate: 0.42 → 0.58 (bearish → neutral)
Consensus: No
Biggest shift: Retail Rachel (+0.37) — influenced by institutional confidence

Full run saved to data/runs/run_2026-04-04_001.json
```

---

## Component 6: API Server

**Responsibility:** HTTP interface for the React UI to submit prompts and retrieve results.

**Tech:** FastAPI. One file.

### Endpoints

```
POST /api/simulate
  Body: {"prompt": "Fed raises rates 50bps", "context": "optional"}
  Response: {"run_id": "run_2026-04-04_001", "status": "completed", ...full run JSON}

  Phase 1: Synchronous — waits for simulation to complete, returns full result.
  Phase 2+: Returns run_id immediately, streams ticks via WebSocket.

GET /api/runs/{run_id}
  Response: Full run JSON from file.

GET /api/runs
  Response: List of past run IDs with scenario titles.
```

**CORS:** Allow `http://localhost:5173` (Vite dev server).

**File:** `src/pythia/api.py`

### CLI Entry Point

```bash
# Run simulation directly
python -m pythia "Fed raises rates 50bps"
python -m pythia "Should I buy or rent in Austin?" --context "I have 50k saved..."

# Start API server for UI
python -m pythia serve
# → FastAPI at http://localhost:8000
```

**File:** `src/pythia/__main__.py`

---

## Component 7: UI Input Bar

**Responsibility:** Add prompt input to the existing React app.

A text input field + "Consult the Oracle" submit button added to the React app. On submit:
1. POST to `/api/simulate` with the prompt
2. Receive the full run JSON
3. Feed it into the existing simulation reducer — Stage, Arena, Temple, AccuracyCurve all render from real data instead of mocks

**Minimal change to existing UI.** The components already accept data in a compatible shape. The main work is:
- Add an input component
- Replace the hardcoded scenario in `useSimulation` with data from the API response
- Map the run JSON agent/tick format to the reducer's expected state shape

**File changes:** `src/ui/src/components/InputBar.jsx` (new), `src/ui/src/App.jsx` (modified), `src/ui/src/pythia/useSimulation.js` (modified)

---

## File Structure

Note: The existing `src/simulation/` directory (empty scaffold from PLAN.md) is replaced by `src/pythia/`. The React simulation logic at `src/ui/src/simulation/` is unrelated and unchanged.

```
src/
├── pythia/                  ← Phase 1 Python backend (python -m pythia)
│   ├── __init__.py
│   ├── __main__.py          ← CLI entry point + "serve" command
│   ├── analyzer.py          ← Scenario Analyzer
│   ├── generator.py         ← Agent Generator
│   ├── engine.py            ← Simulation Engine (tick loop)
│   ├── llm.py               ← Ollama HTTP client
│   ├── models.py            ← Pydantic models for all JSON schemas
│   ├── api.py               ← FastAPI server
│   └── config.py            ← Model name, Ollama URL, tick count defaults
├── ui/                      ← Existing React app (minor additions)
│   └── src/
│       ├── components/
│       │   └── InputBar.jsx ← New: prompt input + submit
│       ├── simulation/
│       │   └── useSimulation.js ← Modified: accept API data
│       └── App.jsx          ← Modified: wire InputBar to simulation
data/
├── runs/                    ← Simulation output JSON files
```

---

## Dependencies

### Python (new `pyproject.toml` at project root)
- `fastapi` — API server
- `uvicorn` — ASGI server for FastAPI
- `httpx` — Async HTTP client for Ollama calls
- `pydantic` — Data validation and JSON schemas

No OASIS, no CAMEL-AI, no LangChain. Four dependencies total.

### Ollama (external, user-installed)
- Ollama running locally with a model pulled (e.g., `ollama pull llama3.1:8b`)

### React (no new dependencies)
- Existing Vite + React setup. InputBar is a plain component, API calls via `fetch`.

---

## What Phase 1 Does NOT Include

- Web search / document ingestion (future: LLM expansion with search)
- Temple of Learning behavioral amendments (Phase 2: Cognee integration)
- Ground truth comparison / real accuracy scoring (Phase 2)
- WebSocket streaming of live ticks (Phase 2+: transport upgrade)
- God's Eye View variable injection mid-simulation (Phase 3 extension)
- Docker deployment (Phase 4)
- Zep Cloud agent memory (future infrastructure)

---

## Success Criteria

1. `python -m pythia "Fed raises rates 50bps"` produces a valid run JSON with 5+ agents and 20 ticks
2. `python -m pythia "Should I buy or rent in Austin?"` produces agents appropriate to a personal decision (advisors, peers) — not traders
3. `python -m pythia "City bans short-term rentals"` produces citizen segments and policymakers — not investors
4. `python -m pythia serve` starts an API that the React UI can submit prompts to and display results
5. Each tick completes in under 10 seconds (parallel Ollama calls for 5-10 agents)
6. Full 20-tick run completes in under 3 minutes on a local 8B model
7. Output JSON is valid and matches the schema defined in this spec
