# UI Redesign: Chart Recorder — Design

**Date:** 2026-09-23
**Status:** Approved (direction, palette, results flow)
**Reference prototype:** `src/ui/public/compare.html` → "Recorder refined", palette "Graphite" (temporary review page; remove once the real UI lands)

## Goal

Replace the current dark-and-gold oracle UI (particle arena, stacked control bars, cramped verdict banner) with a classy, interpretable, instrument-style interface whose motion explains cause and effect, and which stays legible from 3 agents to ensemble scale (40+ trajectories).

## Problems being fixed (from review of the current UI)

- Three stacked control bars and five equal-weight mode buttons before any content.
- The largest area (particle arena) carries the least information; the Temple panel is mostly empty; the agent list clips.
- No text hierarchy (`--text-muted` is `#FFFFFF`).
- Verdict is a cramped bottom banner; "The Oracle's Method" is a config dump; ensemble / backtest / influence / coherence have no home.
- Demo bug: the demo verdict says "leans toward accumulating" while the final aggregate is 0.28 (sell side).

## Direction

**Live view: chart recorder.** A single instrument housing containing:

- **Paper window** — printed chart paper (pale grid, stronger 0.5 line, tick numbers, sprocket holes) scrolling right-to-left at a fixed rate per tick. A fixed scale plate on the left edge (1.0 / 0.5 / 0.0, Buy / Sell).
- **Pens on a rail** — one carriage per camp (camp average, dark ink), one accent carriage for the whole room. Faint lines for every individual agent. Carriages spring-follow their value. Labels right of the rail de-collide and show live values.
- **Event pen** — stamps a mark and an italic label along the top margin whenever an event moves the room (influence message, herd shift, Temple reflection).
- **Readout column** — the room's value (large, accent), plain-language label, change since tick 1; per-camp value and change, highlighted when involved in the current event; an event display that types the current event with a cursor.
- **Status strip** — rolling odometer tick counter; recording lamp (pulses only while recording; distinct paused and complete states); cast size; a one-line legend explaining accent pen, dark pens, faint lines, and top marks.

**End of run.** The paper stops and a verdict card slides over the readout column with the plain-English verdict and a "Read the analysis" link.

**Analysis view (journalism).** Separate page in the same type system: plain-English headline verdict; camps beeswarm (camp cloud, average, change since tick 1); small multiples (one chart per camp plus the whole room); plus the existing decision content (arguments, risks, takeaways, influence, method) re-laid out editorially. Later home for Jev confidence and the stated-vs-expressed stance gap.

## Scaling rule

Agents are grouped into **camps** = the analyzer's archetypes (`AgentArchetype.role`). Pens are per camp, so pen count stays small regardless of cast size; individuals are faint traces. Verified visually at 5, 15, and 40 agents.

## Visual system

- **Type:** Archivo (one family), tabular figures everywhere numbers change.
- **Palette: Graphite** — housing `#212326` on `#141517`, well `#0D0E10`, paper `#F4F4F0` with grid `#E3E6E1 / #CBD1CA / #A9B3A8`, pen ink `#1B1D20`, accent `#E4553B` (text on paper uses `#C9432A`), display glass `#0A0B0C`. Tokens defined once as CSS custom properties; other palettes from the review (warm grey, forest, cobalt, olive) remain as token sets but are not shipped.
- **One accent** = the room. Nothing else uses it except event marks and the involved camp's highlight.
- **Controls:** question field and a single mode rocker (Consult / Oracle loop / Ensemble / Backtest) in the header; simulation size moves into a settings popover; demo remains available.

## Motion rules

- Nothing moves unless the simulation state changed (paper advance, pen movement, event stamp, typing, counter roll, lamp while recording).
- Between SSE tick events, values interpolate with requestAnimationFrame; no layout-affecting animation (transform/opacity/SVG attributes only).
- `prefers-reduced-motion`: paper jumps per tick, no spring, no cursor blink, no lamp pulse.

## Mode behaviour (to be detailed in the implementation plan)

- **Consult:** as above.
- **Oracle loop:** Temple reflections are event-pen marks; run counter joins the status strip; each new run starts a new paper section.
- **Ensemble:** one faint trace per run's room line plus the ensemble mean as the accent pen (open detail).
- **Backtest:** the known outcome is drawn as a target line across the paper.

## Data needed from the backend

- Per-agent camp id (archetype role) in the `scenario` SSE event.
- Events as first-class stream data: influence edges and herd-pressure edges (already in the influence graph), Temple reflections (oracle loop).
- Verdict text consistent with the final aggregate (fix demo; guard in summary).

## Implementation notes

- React components with SVG; no new heavy dependencies. Split the current large components (`InputBar` 743 lines, `DecisionPanel` 624, `App` 591) as part of the rebuild.
- Pure, unit-tested helpers (Vitest): paper scroll math, label de-collision, camp aggregation, event windows.
- Component tests for the recorder and verdict card; visual verification in the browser at 5 / 15 / 40 agents and in reduced-motion mode.
