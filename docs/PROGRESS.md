# Pythia — Project Progress

> Live doc. Updated at the end of each coding session. Read this at the start of every session to restore context.

---

## Session Log

### 2026-04-13
- Implemented Phase 1 (Simulation Backbone) — all 10 tasks, TDD, subagent-driven
- 9 Python modules created: config, models, llm, analyzer, generator, engine, orchestrator, api, __main__
- 47 Python tests passing, 18 UI tests still passing
- Branch `feat/phase1-simulation-backbone` ready to merge

### 2026-04-05
- Designed Phase 1 (Simulation Backbone) end-to-end through brainstorming session
- Key decisions: custom engine (no OASIS/CAMEL-AI), local models via Ollama, structured JSON agent output, dual input (CLI + API)
- Wrote full design spec: `docs/superpowers/specs/2026-04-04-phase1-simulation-backbone-design.md`
- Wrote implementation plan (10 tasks, ~55 TDD steps): `docs/superpowers/plans/2026-04-04-phase1-simulation-backbone.md`
- Wrote design note for Phase 2+ features: `docs/superpowers/specs/2026-04-05-graph-memory-and-self-healing-design-note.md`
- No code written yet — design and planning only

### 2026-04-02
- Built complete React visualization app (`src/ui/`) converting the prototype HTML mock into a testable, componentized SPA
- 11 files implemented across simulation logic and UI components
- 18/18 tests passing (Vitest + jsdom)
- Merged `feat/react-visualization` branch into main and pushed to GitHub
- Set up session automation: SessionStart hook injects this doc, Stop hook auto-pushes commits
- Gitignored sensitive artifacts: `.claude/settings.local.json`, `.playwright-mcp/`, screenshots

---

## Current State — 2026-04-13

**Phase 3 (Frontend Visualization) — COMPLETE**
**Phase 1 (Simulation Backbone) — COMPLETE** (47 Python tests + 18 UI tests passing)
**Phase 2 (Oracle Loop) — DESIGNED (design note), NOT IMPLEMENTED**

The full Phase 1 backend is implemented and tested. The UI is connected to the API via the new InputBar. Live simulation requires Ollama running with a model pulled.

---

## What's Been Built

### Prototype (single HTML file)
- `src/ui/prototype.html` — self-contained visual mock. Dark oracle aesthetic, three-zone layout, animated particles, tick progression. Used to validate the design before React conversion.

### React App (`src/ui/`)
A production-grade React + Vite SPA converting the prototype into a testable, componentized app.

**Simulation logic (pure, tested):**
- `src/simulation/scenarios.js` — scenario data: 5 protagonist archetypes (Loss Aversion, Anchoring Bias, FOMO Drive, Reactance Theory, Social Reactance) + 5 crowd psychology states (Herd Neutrality → Social Contagion → Bandwagon Effect → Groupthink Lock → Deindividuation)
- `src/simulation/reducer.js` — pure state reducer with 7 actions: SPAWN, TICK, SEND_TO_TEMPLE, RETURN_FROM_TEMPLE, MARK_NOT_RETURNING, END_RUN, RESET
- `src/simulation/useSimulation.js` — React hook: wires reducer to real time. Spawns protagonists staggered on load, ticks every 2.3s, sends one agent to Temple at tick 9, returns them at tick 16, tracks accuracy run-over-run

**Components:**
- `Header.jsx` — logo ("Pythia ◈ ORACLE"), active scenario name, TICK counter, RUN counter, ↺ Restart button, gold progress bar
- `Stage.jsx` — left panel (210px): protagonist cards with SVG confidence rings (stroke-dashoffset), pulsing glow, lifecycle fade/translate animations, gold flash on temple return
- `Arena.jsx` — center: Canvas 2D, 290 particles, 5 crowd states with velocity/attraction/chaos forces, smooth color lerp
- `Temple.jsx` — right panel (190px): idle oracle text + active state (spinning SVG arc, protagonist dot, typewriter behavioral amendment)
- `AccuracyCurve.jsx` — footer: SVG polyline + gradient area fill, gold line chart showing improving accuracy run-over-run

**Tests:** 18/18 passing (scenarios + reducer, Vitest + jsdom)

**Design tokens:** `src/index.css` — `#0D0D0B` bg, `#A88C52` gold, Playfair Display / Syne / JetBrains Mono fonts

**To run:** `cd src/ui && npm run dev` → `http://localhost:5173`

---

## What's Been Built (Phase 1 — added 2026-04-13)

### Python Backend (`src/pythia/`)
- `config.py` — OLLAMA_BASE_URL, OLLAMA_MODEL, DEFAULT_TICK_COUNT, RUNS_DIR
- `models.py` — All Pydantic models: AgentArchetype, ScenarioBlueprint, Agent, Relationship, TickAction, TickEvent, TickRecord, RunResult, RunSummary, SimulateRequest
- `llm.py` — LLMClient Protocol + OllamaClient (async, JSON mode, 1-retry on malformed JSON)
- `analyzer.py` — analyze_scenario(): prompt → ScenarioBlueprint via one LLM call
- `generator.py` — generate_agents(): two-pass (parallel per archetype + relationship graph)
- `engine.py` — SimulationEngine: tick loop, AgentMemory, parallel agent reasoning
- `orchestrator.py` — run_simulation(): full pipeline + saves JSON to data/runs/
- `__main__.py` — CLI: `python -m pythia "prompt"` and `python -m pythia serve`
- `api.py` — FastAPI: POST /api/simulate, GET /api/runs, GET /api/runs/{run_id}

### UI Updates (`src/ui/src/`)
- `components/InputBar.jsx` — prompt + context inputs, POSTs to API
- `simulation/scenarios.js` — added scenarioFromRunResult() adapter
- `simulation/useSimulation.js` — added useApiSimulation() hook
- `App.jsx` — rebuilt with InputBar, mock/API mode switching

**Tests:** 47 Python tests + 18 UI tests, all passing

**To run backend:**
```bash
cd /path/to/Pythia && source .venv/bin/activate
python -m pythia "Fed raises rates 50bps"       # CLI
python -m pythia serve                           # API server at :8000
```

## What's NOT Built Yet

### Phase 2 — Oracle loop (design note ready)
Design note: `docs/superpowers/specs/2026-04-05-graph-memory-and-self-healing-design-note.md`

- GraphRAG ingestion layer (Phase 1.5, upstream of Scenario Analyzer)
- Graph agent memory via Zep (replaces flat AgentMemory.for_prompt())
- Temple of Learning: evaluate → amend behavioral_rules → re-run loop
- Cognee integration for skill amendment (or plain LLM calls for v1)

### Phase 3+ extensions
- WebSocket/SSE for live tick streaming to UI
- God's Eye View variable injection mid-simulation
- Cross-simulation Research DAG (Phase 5)
- Docker Compose deployment

---

## Architecture Decisions Recorded

| Decision | Choice | Why |
|----------|--------|-----|
| Agent scale problem | 5–20 protagonist nodes + 290 particle crowd field | 1000+ agents can't be individually rendered; crowd psychology governs the mass |
| Layout | Stage / Arena / Temple (3 zones) | Temple as physical zone has dramatic narrative impact; better than timeline/cards |
| State management | `useReducer` pure function + `useSimulation` hook | No external store needed; reducer is easily testable; hook manages side effects |
| Canvas particles | Canvas 2D + requestAnimationFrame | Simpler than Three.js for 2D dots; no dependency overhead |
| Crowd state | Read from `stateRef` inside RAF loop | Avoids stale closure; crowdStateIndex updates propagate immediately |
| Simulation framework | Custom engine, no OASIS/CAMEL-AI | OASIS is social-media focused; our opinion dynamics model is simpler and more flexible |
| LLM provider | Ollama (local, free) | No API costs during development; swappable to Claude/OpenAI later |
| Agent output format | Structured JSON (stance + action + reasoning + message) | Reliable with small models, maps cleanly to UI, machine-readable |
| Agent memory | Full history, with `for_prompt()` abstraction seam | Fits in 8K context for 20 ticks; seam allows future compression/graph upgrade |
| Input modes | CLI + FastAPI HTTP API | Both supported in Phase 1; UI gets input bar |

---

## Next Session Picks Up At

**Execute Phase 1 implementation plan.** All design work is done.

Plan: `docs/superpowers/plans/2026-04-04-phase1-simulation-backbone.md`

Execution options:
1. **Subagent-driven** (recommended) — dispatch fresh subagent per task, review between tasks
2. **Inline execution** — batch execution with checkpoints

Prerequisites before starting:
- Install Ollama and pull a model: `brew install ollama && ollama pull llama3.1:8b`
- Task 1 (project scaffolding) must complete first, then Tasks 2-3 sequentially, then Tasks 4-5-6 can parallelize
