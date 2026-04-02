# Pythia — Project Progress

> Live doc. Updated at the end of each coding session. Read this at the start of every session to restore context.

---

## Current State — 2026-04-02

**Phase 3 (Frontend Visualization) — COMPLETE**
**Phase 1 & 2 (Backend Simulation Engine) — NOT STARTED**

The visualization UI is fully built and running. The backend that would drive it with real simulation data does not exist yet. The UI currently runs on mock data (hardcoded scenario + timer-driven ticks).

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

## What's NOT Built Yet

### Phase 1 — Simulation backbone
- Document/text ingestion (feed it a decision: "Fed raises rates 50bps")
- GraphRAG entity + relationship extraction
- OASIS agent generation from entities (real archetypes, not hardcoded)
- Basic OASIS simulation run producing tick events

### Phase 2 — Oracle loop
- Cognee integration for skill self-improvement
- Ground truth comparison + accuracy scoring
- Temple of Learning amendment generation (real LLM rewrite, not typewriter mock)
- Cross-simulation Research DAG

### Phase 3 extensions (not yet)
- WebSocket/SSE protocol to stream live sim events to the UI
- God's Eye View variable injection mid-simulation
- Multiple scenario support beyond `market-sentiment`

### Infrastructure
- Docker Compose setup
- Pre-built demo scenarios
- Zep Cloud agent memory integration

---

## Architecture Decisions Recorded

| Decision | Choice | Why |
|----------|--------|-----|
| Agent scale problem | 5–20 protagonist nodes + 290 particle crowd field | 1000+ agents can't be individually rendered; crowd psychology governs the mass |
| Layout | Stage / Arena / Temple (3 zones) | Temple as physical zone has dramatic narrative impact; better than timeline/cards |
| State management | `useReducer` pure function + `useSimulation` hook | No external store needed; reducer is easily testable; hook manages side effects |
| Canvas particles | Canvas 2D + requestAnimationFrame | Simpler than Three.js for 2D dots; no dependency overhead |
| Crowd state | Read from `stateRef` inside RAF loop | Avoids stale closure; crowdStateIndex updates propagate immediately |

---

## Next Session Picks Up At

**Start Phase 1:** Document ingestion → GraphRAG → agent generation → basic OASIS simulation run.

Key questions to resolve before building:
1. Which OASIS version/fork to use? (CAMEL-AI's oasis repo)
2. GraphRAG: Microsoft's GraphRAG, or lighter alternative?
3. Input format for first demo: plain English description, or a news article?

Suggested first task: spike the OASIS integration — get a minimal simulation running in Python that produces tick events, even with hardcoded agents.
