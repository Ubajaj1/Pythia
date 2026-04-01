# Pythia — Frontend Visualization Design Spec
**Date:** 2026-04-01
**Scope:** Real-time simulation visualization UI (Phase 3 of PLAN.md)

---

## Overview

A real-time, single-page visualization that runs during an active Pythia simulation. It shows agents spawning, taking psychological character, making decisions, failing, retraining in the Temple of Learning, and improving over successive runs. The design is minimalistic and dark — serious, not decorative.

---

## Aesthetic

| Property | Value |
|---|---|
| Background | `#0D0D0B` (warm near-black) |
| Zone surfaces | `#141410` / `#16140E` |
| Primary text | `#6A6762` (dark warm gray — data content) |
| UI chrome labels | `#6E6A66` (readable on dark bg) |
| Gold accent | `#A88C52` (muted gold — sole warm accent, oracle/Temple) |
| Font: Display | Playfair Display italic — logo only |
| Font: UI | Syne (variable weight 300–700) — agent names, labels |
| Font: Data | JetBrains Mono — tick counts, confidence %, accuracy |

Zone separation via negative space and subtle background differentiation — no colored borders.

---

## Layout

Three fixed horizontal zones inside a full-viewport dark canvas:

```
┌─────────────────────────────────────────────────────────────┐
│  Pythia ◈ ORACLE    [Scenario Name]    ↺ Restart  TICK 04/20│
├─ progress bar (gold, 1px) ──────────────────────────────────┤
├───────────────────┬─────────────────────┬───────────────────┤
│   // THE STAGE    │    // THE ARENA     │ // TEMPLE OF      │
│   (210px)         │    (flex: 1)        │    LEARNING       │
│                   │                     │   (190px)         │
│  Protagonist      │  Crowd particle     │                   │
│  nodes — named,   │  field — 290 dots   │  Failing agents   │
│  tracked,         │  governed by crowd  │  retraining with  │
│  psych-grounded   │  psychology states  │  gold spinner +   │
│                   │                     │  typewriter amend │
├───────────────────┴─────────────────────┴───────────────────┤
│  PREDICTION ACCURACY  [line chart, gold] ──────── 44%       │
└─────────────────────────────────────────────────────────────┘
```

---

## Zone 1: The Stage (Protagonists)

**What it shows:** 5–20 named protagonist agents, each grounded in an individual psychology concept. These are the decision-makers — the characters whose behavior the simulation tracks.

**Node anatomy (per protagonist):**
- Circle (26px) filled with a unique desaturated warm color per archetype
- Thin SVG arc ring (confidence meter) — drains/fills each tick via `stroke-dashoffset` transition
- Soft pulsing glow — `box-shadow` animation at 2.8s interval
- Label above: agent name in Syne 600
- Label below: psych trait in Syne 300, gold — fades in on spawn
- Confidence % in JetBrains Mono below

**Lifecycle state transitions:**
| State | Visual |
|---|---|
| Spawning | Fade in + scale up from point, 600ms staggered |
| Taking character | Color crystallizes from gray → archetype color; trait label fades in |
| Active | Slow glow pulse |
| Failing → Temple | Node dims to 25% opacity, translates right off-stage |
| Returning from Temple | Slides back, gold flash animation, confidence ring resets high |

**Scenarios drive protagonist roster** — different scenarios load different psychological archetypes (e.g. financial crisis → Loss Aversion, Anchoring Bias, Reactance; product launch → FOMO Drive, Social Proof, Innovator Bias).

---

## Zone 2: The Arena (Crowd Field)

**What it shows:** The crowd — 1000+ agents represented as ~290 rendered particles (3–4px dots). Governed by crowd psychology concepts, not individual psychology. They react to protagonist decisions as a mass.

**Crowd psychology states** (cycle through during a simulation run):
| State | Particle behavior | Color |
|---|---|---|
| Herd Neutrality | Random slow drift, scattered | Cool gray `#3A3A38` |
| Social Contagion | Begin flowing toward center | Warming toward off-white |
| Bandwagon Effect | Clustering, accelerating | Bright off-white clusters |
| Groupthink Lock | Dense mass, nearly uniform | Near-white, tightly packed |
| Deindividuation | Rapid chaotic scatter | Red-tinted `#8A5045` |

State transitions are fluid (lerp on `ct` per particle, no hard cuts). Current state label shown in JetBrains Mono at bottom of arena.

**Implementation:** Canvas 2D API, `requestAnimationFrame` loop. Particles use velocity + attraction force toward cluster center (configurable per state) + chaos factor for panic states.

---

## Zone 3: Temple of Learning

**What it shows:** The self-correction zone. When a protagonist fails (confidence collapses), they animate into this zone between ticks. Their behavioral rules are rewritten here.

**Visual identity:** Background warms slightly to `#16140E`. Radial gradient glow at bottom (`rgba(196,169,106,0.07)`) — ambient oracle fire. No hard border.

**Idle state:** Centered Playfair Display italic text — *"The oracle awaits the fallen"* — flanked by thin gold divider lines.

**Active state (agent retraining):**
- Protagonist's colored dot appears in center
- Rotating gold arc spinner (3.5s linear, `stroke-dasharray` gap effect)
- Agent name in gold
- Typewriter text: behavioral amendment being written, letter by letter (JetBrains Mono 8.5px)
- On completion: agent slides back to Stage with a gold flash

**Logic:** At tick 9, one failing protagonist is selected and sent to Temple. At tick 16, they return. On run end, any temple agent is returned and confidence resets.

---

## Header & Footer

**Header:**
- Left: *Pythia* in Playfair Display italic + `◈ ORACLE` in Syne 300 gold
- Center: scenario label (Syne 300 uppercase, muted) + scenario name (Syne 500)
- Right: ↺ Restart button (JetBrains Mono, gold border) + `TICK 04 / 20` + `RUN · 01`

**Progress bar:** 1px gold line beneath header, fills left-to-right each tick.

**Footer — Accuracy curve:**
- SVG line chart (`viewBox="0 0 500 32"`, `preserveAspectRatio="none"`)
- X-axis: run number. Y-axis: prediction accuracy (30–100% range).
- Gold polyline + gold gradient area fill below the line
- Current accuracy value in JetBrains Mono 20px at right
- Accuracy improves run-over-run as Temple-returned agents perform better

---

## Simulation Timing (Mock)

| Event | Timing |
|---|---|
| Protagonist spawn stagger | 320ms apart, starting 600ms after load |
| First accuracy point | 1800ms after load |
| Tick interval | 2300ms per tick |
| Temple entry | Tick 9 |
| Temple exit | Tick 16 |
| Run length | 20 ticks |

In production these will be driven by real OASIS simulation events via WebSocket or SSE.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Framework | React (per PLAN.md) |
| Canvas particles | Canvas 2D API + `requestAnimationFrame` |
| Confidence rings | SVG `stroke-dashoffset` transitions |
| Accuracy chart | SVG `polyline` + gradient `path` |
| Animations | CSS transitions + `@keyframes` |
| Fonts | Google Fonts (Playfair Display, Syne, JetBrains Mono) |
| State management | Local component state (no external store needed at this stage) |

---

## What This Spec Does NOT Cover

- Backend integration (WebSocket/SSE event protocol) — separate spec
- God's Eye View variable injection UI — Phase 3 extension
- Multi-run comparison view — future
- Mobile / responsive layout — desktop-first for now
