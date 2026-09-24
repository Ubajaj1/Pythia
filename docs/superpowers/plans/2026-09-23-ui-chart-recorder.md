# UI Redesign: Chart Recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the particle-arena UI with the approved chart-recorder live view (Graphite palette, Archivo), an end-of-run verdict card, and a journalism-style analysis page, legible from 3 to 40+ agents.

**Architecture:** A new `src/ui/src/recorder/` module holds pure data functions (`model.js`, fully unit-tested), a requestAnimationFrame clock hook, and small presentational components (`ChartPaper`, `Readout`, `EventGlass`, `StatusStrip`, `VerdictCard`) assembled by `Recorder.jsx`. Stream parsing moves out of `InputBar` into `api/streams.js`. `App.jsx` keeps raw stream data (scenario, ticks, influence, run events) and routes the live view to `Recorder`. The analysis page lives in `src/ui/src/analysis/`. Old components are deleted only in the last task, so every intermediate commit runs.

**Tech Stack:** React 19, Vite, Vitest + @testing-library/react + jsdom, inline SVG, plain CSS with custom properties. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-23-ui-redesign-design.md`. Visual reference: `src/ui/public/compare.html` → "Recorder refined", palette Graphite (function `B4`).

## Global Constraints

- Branch `feat/ui-chart-recorder` from `origin/main` **after** backend-refresh has merged (the recorder consumes `AgentInfo.camp`, `influence` events, `quality`, and `decision_summary.verdict_label`).
- Palette: Graphite tokens exactly as in Task 1's CSS; one accent (`--accent #E4553B`, text on paper `--accentInk #C9432A`) used only for the room pen, room value, event marks, and the involved camp's highlight.
- Type: Archivo (Google Fonts link, weights 400/500/600, italic 400) with `font-variant-numeric: tabular-nums` on the recorder root.
- Copy rules: sentence case; no em or en dashes in UI strings; at most one `·` separator per line.
- Motion only on state change. `prefers-reduced-motion: reduce` → paper jumps per tick, no carriage transition, no cursor blink, no lamp pulse.
- Paper geometry constants (viewBox units): `W=1040, H=640, RAIL=800, PPT=48, PLATE=50, PY0=48, PY1=596`.
- Frontend tests: `cd src/ui && npx vitest run`. All pre-existing tests stay green until Task 10 deletes the modules they cover.

---

### Task 1: Tokens, fonts, and the recorder model

**Files:**
- Create: `src/ui/src/recorder/recorder.css`
- Create: `src/ui/src/recorder/model.js`
- Modify: `src/ui/index.html` (fonts link)
- Test: `src/ui/src/recorder/model.test.js`

**Interfaces:**
- Produces (all exported from `model.js`):
  - `campOf(agent) -> string`
  - `groupCamps(agents) -> Array<{ id: string, name: string, agentIds: string[] }>`
  - `buildSeries(agents, ticks) -> { byAgent: Record<string, number[]>, room: number[] }` (index 0 = initial stance, index k = after tick k)
  - `campSeries(byAgent, camps) -> Record<string, number[]>`
  - `valueAt(series: number[], t: number) -> number` (linear interpolation, clamped)
  - `stanceLabel(v: number, spectrum: string[]) -> string`
  - `momentsFromInfluence(influence: Array<{tick, edges}>, agentsById, minDelta = 0.05) -> Moment[]`
  - `reflectMoment(runComplete, agentsById, atTick = 0) -> Moment | null`
  - `MOMENT_WINDOW = 3.2`; `activeMoment(moments, t, win = MOMENT_WINDOW) -> Moment | null`
  - `declutter(items: Array<{id, y}>, minGap, lo, hi) -> Record<string, number>`
  - `advanceClock(t, available, dtMs, msPerTick) -> number`
  - `Moment = { tick: number, kind: 'message' | 'herd' | 'reflect', label: string, text: string, targetId?: string, sourceId?: string }`

- [ ] **Step 1: Branch**

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
git checkout -b feat/ui-chart-recorder
```

- [ ] **Step 2: Write the failing tests** — `src/ui/src/recorder/model.test.js`

```js
import { describe, it, expect } from 'vitest'
import {
  activeMoment, advanceClock, buildSeries, campSeries, declutter, groupCamps,
  momentsFromInfluence, reflectMoment, stanceLabel, valueAt,
} from './model.js'

const agents = [
  { id: 'a', name: 'Ann', camp: 'Retail', initial_stance: 0.4 },
  { id: 'b', name: 'Ben', camp: 'Retail', initial_stance: 0.6 },
  { id: 'c', name: 'Cy', role: 'Institutional', initial_stance: 0.5 },
]
const ticks = [
  { tick: 1, events: [{ agent_id: 'a', stance: 0.3 }, { agent_id: 'b', stance: 0.5 }, { agent_id: 'c', stance: 0.5 }] },
  { tick: 2, events: [{ agent_id: 'a', stance: 0.2 }, { agent_id: 'c', stance: 0.6 }] },
]

describe('groupCamps', () => {
  it('groups by camp, falling back to role, in first-seen order', () => {
    expect(groupCamps(agents)).toEqual([
      { id: 'Retail', name: 'Retail', agentIds: ['a', 'b'] },
      { id: 'Institutional', name: 'Institutional', agentIds: ['c'] },
    ])
  })
})

describe('buildSeries', () => {
  it('starts at the initial stance and carries missing agents forward', () => {
    const { byAgent, room } = buildSeries(agents, ticks)
    expect(byAgent.a).toEqual([0.4, 0.3, 0.2])
    expect(byAgent.b).toEqual([0.6, 0.5, 0.5])
    expect(room[0]).toBeCloseTo(0.5)
    expect(room[2]).toBeCloseTo((0.2 + 0.5 + 0.6) / 3)
  })
  it('camp series averages members', () => {
    const { byAgent } = buildSeries(agents, ticks)
    const cs = campSeries(byAgent, groupCamps(agents))
    expect(cs.Retail).toEqual([0.5, 0.4, 0.35])
  })
})

describe('valueAt', () => {
  it('interpolates and clamps', () => {
    expect(valueAt([0, 1], 0.25)).toBeCloseTo(0.25)
    expect(valueAt([0, 1], 5)).toBe(1)
    expect(valueAt([], 1)).toBe(0.5)
  })
})

describe('stanceLabel', () => {
  it('maps to the five-label spectrum', () => {
    const sp = ['Strong sell', 'Leaning sell', 'Neutral', 'Leaning buy', 'Strong buy']
    expect(stanceLabel(0.28, sp)).toBe('Leaning sell')
    expect(stanceLabel(1, sp)).toBe('Strong buy')
  })
})

describe('moments', () => {
  const byId = Object.fromEntries(agents.map(a => [a.id, a]))
  it('picks the strongest message edge per tick', () => {
    const m = momentsFromInfluence([{ tick: 2, edges: [
      { edge_type: 'message', source_id: 'c', target_id: 'a', influence_delta: -0.02, message: 'x' },
      { edge_type: 'message', source_id: 'b', target_id: 'a', influence_delta: -0.1, message: 'Get out.' },
    ] }], byId)
    expect(m).toEqual([{ tick: 2, kind: 'message', label: 'Ben to Ann', text: '“Get out.”', targetId: 'a', sourceId: 'b' }])
  })
  it('reports herd drift when two or more agents follow the room', () => {
    const m = momentsFromInfluence([{ tick: 3, edges: [
      { edge_type: 'herd_pressure', source_id: '__aggregate__', target_id: 'a', influence_delta: -0.03, message: '' },
      { edge_type: 'herd_pressure', source_id: '__aggregate__', target_id: 'b', influence_delta: -0.03, message: '' },
    ] }], byId)
    expect(m[0].kind).toBe('herd')
    expect(m[0].label).toBe('Room drifts')
  })
  it('ignores ticks with weak influence', () => {
    expect(momentsFromInfluence([{ tick: 1, edges: [{ edge_type: 'message', source_id: 'a', target_id: 'b', influence_delta: 0.01, message: 'm' }] }], byId)).toEqual([])
  })
  it('reflect moment names the amended agents', () => {
    const m = reflectMoment({ run_number: 1, amended_agent_ids: ['a', 'c'] }, byId)
    expect(m.kind).toBe('reflect')
    expect(m.text).toMatch(/Ann and Cy/)
    expect(reflectMoment({ run_number: 1, amended_agent_ids: [] }, byId)).toBeNull()
  })
  it('activeMoment returns the latest started moment inside the window', () => {
    const ms = [{ tick: 8 }, { tick: 11 }]
    expect(activeMoment(ms, 12)).toEqual({ tick: 11 })
    expect(activeMoment(ms, 7.9)).toBeNull()
    expect(activeMoment(ms, 15)).toBeNull()
  })
})

describe('declutter', () => {
  it('keeps a minimum gap and stays inside bounds', () => {
    const out = declutter([{ id: 'x', y: 100 }, { id: 'y', y: 105 }, { id: 'z', y: 590 }, { id: 'w', y: 595 }], 24, 50, 600)
    expect(out.y - out.x).toBeGreaterThanOrEqual(24)
    expect(out.w).toBeLessThanOrEqual(600)
    expect(out.w - out.z).toBeGreaterThanOrEqual(24)
  })
})

describe('advanceClock', () => {
  it('moves toward the available tick and never past it', () => {
    expect(advanceClock(0, 3, 600, 1200)).toBeCloseTo(0.5)
    expect(advanceClock(2.9, 3, 1200, 1200)).toBe(3)
    expect(advanceClock(3, 3, 1200, 1200)).toBe(3)
  })
})
```

- [ ] **Step 3: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/model.test.js`
Expected: FAIL (cannot resolve `./model.js`).

- [ ] **Step 4: Implement `src/ui/src/recorder/model.js`**

```js
// Pure data functions for the chart recorder. No React, no DOM.

const mean = xs => xs.reduce((s, x) => s + x, 0) / (xs.length || 1)

export function campOf(agent) {
  return agent.camp || agent.role || 'Panel'
}

export function groupCamps(agents) {
  const order = []
  const members = new Map()
  for (const a of agents) {
    const c = campOf(a)
    if (!members.has(c)) { members.set(c, []); order.push(c) }
    members.get(c).push(a.id)
  }
  return order.map(id => ({ id, name: id, agentIds: members.get(id) }))
}

export function buildSeries(agents, ticks) {
  const byAgent = Object.fromEntries(agents.map(a => [a.id, [a.initial_stance]]))
  const sorted = [...ticks].sort((x, y) => x.tick - y.tick)
  for (const tk of sorted) {
    const seen = new Set()
    for (const e of tk.events) {
      if (byAgent[e.agent_id]) { byAgent[e.agent_id].push(e.stance); seen.add(e.agent_id) }
    }
    for (const a of agents) {
      if (!seen.has(a.id)) { const s = byAgent[a.id]; s.push(s[s.length - 1]) }
    }
  }
  const n = sorted.length + 1
  const room = Array.from({ length: n }, (_, i) => mean(agents.map(a => byAgent[a.id][i])))
  return { byAgent, room }
}

export function campSeries(byAgent, camps) {
  return Object.fromEntries(camps.map(c => {
    const len = byAgent[c.agentIds[0]].length
    return [c.id, Array.from({ length: len }, (_, i) => mean(c.agentIds.map(id => byAgent[id][i])))]
  }))
}

export function valueAt(series, t) {
  if (!series.length) return 0.5
  const x = Math.max(0, Math.min(series.length - 1, t))
  const i = Math.floor(x)
  const f = x - i
  return i + 1 < series.length ? series[i] + (series[i + 1] - series[i]) * f : series[i]
}

export function stanceLabel(v, spectrum) {
  const i = Math.min(Math.floor(v * spectrum.length), spectrum.length - 1)
  return spectrum[Math.max(0, i)]
}

const nameOf = (byId, id) => byId[id]?.name ?? id

export function momentsFromInfluence(influence, agentsById, minDelta = 0.05) {
  const out = []
  for (const { tick, edges } of influence) {
    const msgs = edges.filter(e => e.edge_type === 'message' && Math.abs(e.influence_delta) >= minDelta)
    if (msgs.length) {
      const top = msgs.reduce((a, b) => (Math.abs(b.influence_delta) > Math.abs(a.influence_delta) ? b : a))
      out.push({
        tick, kind: 'message',
        label: `${nameOf(agentsById, top.source_id)} to ${nameOf(agentsById, top.target_id)}`,
        text: `“${top.message}”`, targetId: top.target_id, sourceId: top.source_id,
      })
      continue
    }
    const herd = edges.filter(e => e.edge_type === 'herd_pressure')
    if (herd.length >= 2) {
      out.push({ tick, kind: 'herd', label: 'Room drifts', text: `The room shifted and ${herd.length} agents followed it.`, targetId: herd[0].target_id })
    }
  }
  return out
}

export function reflectMoment(runComplete, agentsById, atTick = 0) {
  const ids = runComplete.amended_agent_ids || []
  if (!ids.length) return null
  const names = ids.map(id => nameOf(agentsById, id))
  const list = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
  return {
    tick: atTick, kind: 'reflect',
    label: `${names.length} reflect${names.length === 1 ? 's' : ''}`,
    text: `${list} contradicted their own reasoning and ${names.length === 1 ? 'was' : 'were'} sent to reflect.`,
    targetId: ids[0],
  }
}

export const MOMENT_WINDOW = 3.2

export function activeMoment(moments, t, win = MOMENT_WINDOW) {
  let best = null
  for (const m of moments) {
    if (t >= m.tick && t <= m.tick + win && (!best || m.tick >= best.tick)) best = m
  }
  return best
}

export function declutter(items, minGap, lo, hi) {
  const sorted = [...items].sort((a, b) => a.y - b.y)
  const out = {}
  let prev = -Infinity
  for (const it of sorted) { const ly = Math.max(it.y, lo, prev + minGap); out[it.id] = ly; prev = ly }
  let next = hi
  for (let i = sorted.length - 1; i >= 0; i--) {
    const id = sorted[i].id
    out[id] = Math.min(out[id], next)
    next = out[id] - minGap
  }
  return out
}

export function advanceClock(t, available, dtMs, msPerTick) {
  return Math.min(available, t + dtMs / msPerTick)
}
```

- [ ] **Step 5: Run tests**

Run: `cd src/ui && npx vitest run src/recorder/model.test.js`
Expected: all pass.

- [ ] **Step 6: Tokens and fonts**

`src/ui/src/recorder/recorder.css`:

```css
.rec {
  --bg:#141517; --housing:#212326; --well:#0D0E10; --field:#191A1D; --fieldTx:#A3A7AE;
  --rocker:#191A1D; --rockerOn:#34373C; --ink:#EDEEF0; --dim:#8C9098; --hl:rgba(255,255,255,.06); --line:#3A3D42;
  --paper:#F4F4F0; --plate:#E6E6E1; --plateTx:#5E6166; --grid:#E3E6E1; --grid2:#CBD1CA; --grid3:#A9B3A8; --gtxt:#859085;
  --pen:#1B1D20; --accent:#E4553B; --accentInk:#C9432A; --glass:#0A0B0C; --glassTx:#E8E9EA; --rail:#6B6F76;
  font-family:'Archivo',system-ui,sans-serif; font-variant-numeric:tabular-nums;
  background:var(--bg); color:var(--ink); min-height:100dvh; display:grid; grid-template-rows:76px 1fr 76px;
}
.rec-main { display:grid; grid-template-columns:minmax(0,1fr) 280px; gap:20px; margin:0 32px; padding:20px;
  border-radius:22px; background:var(--housing); box-shadow:0 1px 0 var(--hl) inset, 0 18px 40px rgba(0,0,0,.18); min-height:0; }
.rec-well { border-radius:12px; background:var(--well); box-shadow:inset 0 2px 6px rgba(0,0,0,.35); padding:4px; min-height:0; }
.rec-well svg { width:100%; height:100%; display:block; }
.rec-carriage { transition:transform 180ms cubic-bezier(.2,.8,.2,1); }
.rec-glass { background:var(--glass); color:var(--glassTx); border-radius:12px; padding:16px 18px;
  box-shadow:inset 0 2px 8px rgba(0,0,0,.55), 0 1px 0 var(--hl); }
.rec-glass .t { font-size:13px; opacity:.6; }
.rec-glass .m { font-size:17px; line-height:1.45; margin-top:8px; }
.rec-cursor { display:inline-block; width:9px; height:17px; margin-left:2px; vertical-align:-3px; background:var(--glassTx); animation:rec-blink 1s steps(1) infinite; }
.rec-win { width:30px; height:42px; overflow:hidden; border-radius:6px; background:var(--glass); box-shadow:inset 0 2px 5px rgba(0,0,0,.6); }
.rec-strip { transition:transform .45s cubic-bezier(.2,.8,.2,1); }
.rec-strip div { height:42px; line-height:42px; text-align:center; font-size:26px; font-weight:500; color:var(--glassTx); }
.rec-lamp { width:11px; height:11px; border-radius:50%; background:var(--line); }
.rec-lamp.on { background:var(--accent); animation:rec-pulse 1.6s ease-in-out infinite; }
@keyframes rec-blink { 50% { opacity:0; } }
@keyframes rec-pulse { 50% { opacity:.45; } }
@media (prefers-reduced-motion: reduce) {
  .rec-carriage, .rec-strip { transition:none; }
  .rec-cursor, .rec-lamp.on { animation:none; }
}
@media (max-width: 900px) {
  .rec-main { grid-template-columns:1fr; margin:0 16px; }
}
```

In `src/ui/index.html`, append `&family=Archivo:ital,wght@0,400;0,500;0,600;1,400` to the existing Google Fonts `family=` list (keep the old families until Task 10).

- [ ] **Step 7: Commit**

```bash
git add src/ui/src/recorder/model.js src/ui/src/recorder/model.test.js src/ui/src/recorder/recorder.css src/ui/index.html
git commit -m "feat(ui): recorder data model and Graphite tokens"
```

---

### Task 2: Clock hook

**Files:**
- Create: `src/ui/src/recorder/useRecorderClock.js`
- Test: `src/ui/src/recorder/useRecorderClock.test.jsx`

**Interfaces:**
- Consumes: `advanceClock` (Task 1)
- Produces: `usePrefersReducedMotion() -> boolean`; `useRecorderClock(available: number, { msPerTick = 1200, paused = false } = {}) -> number` (float tick position, 0 = initial)

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRecorderClock } from './useRecorderClock.js'

function mockMatchMedia(reduce) {
  window.matchMedia = vi.fn().mockImplementation(q => ({
    matches: reduce && q.includes('reduce'), media: q,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
}

describe('useRecorderClock', () => {
  let now = 0
  let frames = []
  beforeEach(() => {
    now = 0; frames = []
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    window.requestAnimationFrame = cb => { frames.push(cb); return frames.length }
    window.cancelAnimationFrame = () => {}
  })
  afterEach(() => vi.restoreAllMocks())

  const flush = ms => act(() => { now += ms; const f = frames; frames = []; f.forEach(cb => cb(now)) })

  it('advances toward available ticks over time', () => {
    mockMatchMedia(false)
    const { result } = renderHook(() => useRecorderClock(2, { msPerTick: 1000 }))
    flush(500)
    expect(result.current).toBeCloseTo(0.5)
    flush(5000)
    expect(result.current).toBe(2)
  })

  it('jumps straight to available ticks under reduced motion', () => {
    mockMatchMedia(true)
    const { result } = renderHook(() => useRecorderClock(3))
    expect(result.current).toBe(3)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/useRecorderClock.test.jsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

```js
import { useEffect, useRef, useState } from 'react'
import { advanceClock } from './model.js'

export function usePrefersReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(query)
    if (!mq) return
    const onChange = e => setReduced(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

export function useRecorderClock(available, { msPerTick = 1200, paused = false } = {}) {
  const reduced = usePrefersReducedMotion()
  const [t, setT] = useState(reduced ? available : 0)
  const availableRef = useRef(available)
  availableRef.current = available

  useEffect(() => {
    if (reduced) setT(available)
  }, [reduced, available])

  useEffect(() => {
    if (paused || reduced) return
    let raf
    let last = performance.now()
    const step = now => {
      const dt = now - last
      last = now
      setT(prev => advanceClock(prev, availableRef.current, dt, msPerTick))
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [paused, reduced, msPerTick])

  return t
}
```

- [ ] **Step 4: Run tests**

Run: `cd src/ui && npx vitest run src/recorder/useRecorderClock.test.jsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/recorder/useRecorderClock.js src/ui/src/recorder/useRecorderClock.test.jsx
git commit -m "feat(ui): recorder clock with reduced-motion support"
```

---

### Task 3: ChartPaper

**Files:**
- Create: `src/ui/src/recorder/ChartPaper.jsx`
- Test: `src/ui/src/recorder/ChartPaper.test.jsx`

**Interfaces:**
- Consumes: `valueAt`, `declutter`, geometry constants
- Produces: `<ChartPaper camps agentSeries campSeries roomSeries moments t totalTicks target? faintRooms? />` where `camps: {id,name}[]`, `agentSeries: Record<id, number[]>`, `campSeries: Record<campId, number[]>`, `roomSeries: number[]`, `moments: Moment[]`, `t: number`, `totalTicks: number`, `target: number | null` (backtest actual outcome), `faintRooms: number[][]` (ensemble: previous runs' room series). Test ids: `pen-<campId>`, `pen-room`, `label-<campId>`, `label-room`, `target-line`.

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChartPaper from './ChartPaper.jsx'

const props = {
  camps: [{ id: 'Retail', name: 'Retail' }, { id: 'Institutional', name: 'Institutional' }],
  agentSeries: { a: [0.4, 0.3], b: [0.6, 0.6] },
  campSeries: { Retail: [0.4, 0.3], Institutional: [0.6, 0.6] },
  roomSeries: [0.5, 0.45],
  moments: [{ tick: 1, kind: 'message', label: 'Ben to Ann', text: '“x”' }],
  t: 1, totalTicks: 5, target: null, faintRooms: [],
}

describe('ChartPaper', () => {
  it('draws one pen per camp plus the room pen, with live labels', () => {
    render(<ChartPaper {...props} />)
    expect(screen.getByTestId('pen-Retail')).toBeInTheDocument()
    expect(screen.getByTestId('pen-Institutional')).toBeInTheDocument()
    expect(screen.getByTestId('pen-room')).toBeInTheDocument()
    expect(screen.getByTestId('label-room')).toHaveTextContent('The room')
    expect(screen.getByTestId('label-room')).toHaveTextContent('0.45')
  })
  it('prints event marks along the top', () => {
    render(<ChartPaper {...props} />)
    expect(screen.getByText('Ben to Ann')).toBeInTheDocument()
  })
  it('draws the backtest target line when given', () => {
    render(<ChartPaper {...props} target={0.3} />)
    expect(screen.getByTestId('target-line')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/ChartPaper.test.jsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `ChartPaper.jsx`**

```jsx
import { declutter, valueAt } from './model.js'

export const W = 1040, H = 640, RAIL = 800, PPT = 48, PLATE = 50, PY0 = 48, PY1 = 596
const Y = v => PY1 - v * (PY1 - PY0)
const X = (k, t) => RAIL - (t - k) * PPT

function pathFor(series, t) {
  const from = Math.max(0, t - (RAIL - PLATE) / PPT)
  let d = ''
  for (let x = from; x < t; x += 0.2) d += `${d ? 'L' : 'M'}${X(x, t).toFixed(1)} ${Y(valueAt(series, x)).toFixed(1)}`
  return `${d || 'M'}${d ? 'L' : ''}${RAIL} ${Y(valueAt(series, t)).toFixed(1)}`
}

function Carriage({ y, color }) {
  return (
    <g className="rec-carriage" style={{ transform: `translateY(${y}px)` }}>
      <rect x={RAIL + 4} y={-6} width={22} height={12} rx={3} fill={color} />
      <rect x={RAIL + 7} y={-3.5} width={6} height={2} rx={1} fill="rgba(255,255,255,.35)" />
      <path d={`M${RAIL + 4} -3.5 L${RAIL - 2} 0 L${RAIL + 4} 3.5 Z`} fill={color} />
    </g>
  )
}

export default function ChartPaper({ camps, agentSeries, campSeries, roomSeries, moments, t, totalTicks, target = null, faintRooms = [] }) {
  const gridH = []
  for (let v = 0; v <= 1.0001; v += 0.05) gridH.push(v)
  const gridV = []
  for (let k = Math.ceil((t - (RAIL - PLATE) / PPT) * 2) / 2; k <= t + (W - RAIL) / PPT; k += 0.5) if (X(k, t) >= PLATE) gridV.push(k)
  const off = ((t * PPT) % 26 + 26) % 26
  const holes = []
  for (let x = PLATE + 26 - off; x < W; x += 26) holes.push(x)

  const pens = [
    ...camps.map(c => ({ id: c.id, name: c.name, v: valueAt(campSeries[c.id], t), color: 'var(--pen)', text: 'var(--pen)' })),
    { id: 'room', name: 'The room', v: valueAt(roomSeries, t), color: 'var(--accent)', text: 'var(--accentInk)' },
  ]
  const ly = declutter(pens.map(p => ({ id: p.id, y: Y(p.v) })), 24, PY0, PY1 + 10)
  const faint = N => (N > 15 ? 0.13 : 0.22)
  const agentIds = Object.keys(agentSeries)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Chart recorder: stance of each camp and the whole room over time">
      <defs>
        <clipPath id="rec-paper"><rect x={PLATE} y={0} width={RAIL - PLATE} height={H} /></clipPath>
      </defs>
      <rect x={0} y={0} width={W} height={H} rx={8} fill="var(--paper)" />
      {gridH.map(v => {
        const major = Math.round(v * 20) % 2 === 0, mid = Math.abs(v - 0.5) < 0.01
        return <line key={v} x1={PLATE} x2={W} y1={Y(v)} y2={Y(v)} stroke={mid ? 'var(--grid3)' : major ? 'var(--grid2)' : 'var(--grid)'} strokeWidth={mid ? 1.2 : 1} />
      })}
      {gridV.map(k => {
        const major = Math.abs(k - Math.round(k)) < 0.01
        return (
          <g key={k}>
            <line x1={X(k, t)} x2={X(k, t)} y1={PY0 - 8} y2={PY1 + 8} stroke={major ? 'var(--grid2)' : 'var(--grid)'} />
            {major && k >= 1 && k <= totalTicks && <text x={X(k, t)} y={PY1 + 24} textAnchor="middle" fontSize={11} fill="var(--gtxt)">{Math.round(k)}</text>}
          </g>
        )
      })}
      {holes.map(x => (
        <g key={x}>
          <circle cx={x} cy={14} r={2.6} fill="var(--well)" fillOpacity={0.45} />
          <circle cx={x} cy={H - 14} r={2.6} fill="var(--well)" fillOpacity={0.45} />
        </g>
      ))}
      {moments.filter(m => m.tick <= t && X(m.tick, t) > PLATE + 4).map(m => (
        <g key={`${m.kind}-${m.tick}`}>
          <line x1={X(m.tick, t)} x2={X(m.tick, t)} y1={28} y2={40} stroke="var(--accent)" strokeWidth={2} />
          <text x={X(m.tick, t) - 6} y={38} textAnchor="end" fontSize={12} fontStyle="italic" fill="var(--pen)">{m.label}</text>
        </g>
      ))}
      <g clipPath="url(#rec-paper)">
        {agentIds.map(id => <path key={id} d={pathFor(agentSeries[id], t)} fill="none" stroke="var(--pen)" strokeWidth={0.7} strokeOpacity={faint(agentIds.length)} />)}
        {faintRooms.map((r, i) => <path key={`fr${i}`} d={pathFor(r, r.length - 1)} fill="none" stroke="var(--accent)" strokeWidth={1.2} strokeOpacity={0.35} />)}
        {camps.map(c => <path key={c.id} data-testid={`pen-${c.id}`} d={pathFor(campSeries[c.id], t)} fill="none" stroke="var(--pen)" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />)}
        <path data-testid="pen-room" d={pathFor(roomSeries, t)} fill="none" stroke="var(--accent)" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {target != null && (
        <g data-testid="target-line">
          <line x1={PLATE} x2={W} y1={Y(target)} y2={Y(target)} stroke="var(--accentInk)" strokeDasharray="6 5" />
          <text x={PLATE + 8} y={Y(target) - 6} fontSize={12} fill="var(--accentInk)">Actual outcome {target.toFixed(2)}</text>
        </g>
      )}
      <rect x={0} y={0} width={PLATE} height={H} fill="var(--plate)" />
      <line x1={PLATE} x2={PLATE} y1={0} y2={H} stroke="var(--grid2)" />
      {[[1, '1.0'], [0.5, '0.5'], [0, '0.0']].map(([v, l]) => (
        <text key={l} x={PLATE - 12} y={Y(v) + 4} textAnchor="end" fontSize={11} fill="var(--plateTx)">{l}</text>
      ))}
      <text x={10} y={Y(0.88)} fontSize={12} fontWeight={500} fill="var(--pen)">Buy</text>
      <text x={10} y={Y(0.12) + 8} fontSize={12} fontWeight={500} fill="var(--pen)">Sell</text>
      <line x1={RAIL} x2={RAIL} y1={18} y2={H - 18} stroke="var(--rail)" strokeWidth={3.5} strokeLinecap="round" />
      <line x1={RAIL + 1.6} x2={RAIL + 1.6} y1={20} y2={H - 20} stroke="rgba(255,255,255,.7)" />
      {pens.map(p => (
        <g key={p.id}>
          <Carriage y={Y(p.v)} color={p.color} />
          <path d={`M${RAIL + 27} ${Y(p.v)} C${RAIL + 38} ${Y(p.v)} ${RAIL + 36} ${ly[p.id]} ${RAIL + 48} ${ly[p.id]}`} fill="none" stroke={p.color} strokeWidth={0.8} strokeOpacity={0.6} />
          <text data-testid={`label-${p.id}`} x={RAIL + 54} y={ly[p.id] + 5} fontSize={14} fontWeight={p.id === 'room' ? 600 : 500} fill={p.text}>
            {p.name}
            <tspan x={W - 18} textAnchor="end" fill={p.id === 'room' ? 'var(--accentInk)' : 'var(--plateTx)'}>{p.v.toFixed(2)}</tspan>
          </text>
        </g>
      ))}
    </svg>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `cd src/ui && npx vitest run src/recorder/ChartPaper.test.jsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/recorder/ChartPaper.jsx src/ui/src/recorder/ChartPaper.test.jsx
git commit -m "feat(ui): chart paper with camp pens, room pen, event marks"
```

---

### Task 4: Readout, event glass, status strip

**Files:**
- Create: `src/ui/src/recorder/Readout.jsx`, `EventGlass.jsx`, `StatusStrip.jsx`
- Test: `src/ui/src/recorder/panels.test.jsx`

**Interfaces:**
- Produces:
  - `<Readout room: number, roomStart: number, spectrum: string[], camps: {id,name}[], campValues: Record<id, number>, campStarts: Record<id, number>, highlightCampId?: string />`
  - `<EventGlass moment: Moment | null, t: number, done: boolean, verdict?: string />` (types `moment.text` over 1.4 ticks)
  - `<StatusStrip t: number, totalTicks: number, status: 'recording' | 'paused' | 'complete', nAgents: number, nCamps: number, runLabel?: string />`

- [ ] **Step 1: Write the failing tests**

```jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Readout from './Readout.jsx'
import EventGlass from './EventGlass.jsx'
import StatusStrip from './StatusStrip.jsx'

const sp = ['Strong sell', 'Leaning sell', 'Neutral', 'Leaning buy', 'Strong buy']

describe('Readout', () => {
  it('shows the room value, label, change, and camps', () => {
    render(<Readout room={0.31} roomStart={0.45} spectrum={sp}
      camps={[{ id: 'Retail', name: 'Retail' }]} campValues={{ Retail: 0.25 }} campStarts={{ Retail: 0.4 }} highlightCampId="Retail" />)
    expect(screen.getByText('0.31')).toBeInTheDocument()
    expect(screen.getByText('Leaning sell')).toBeInTheDocument()
    expect(screen.getByText('Down 0.14 since tick 1')).toBeInTheDocument()
    expect(screen.getByText('Retail')).toHaveAttribute('data-hot', 'true')
    expect(screen.getByText('down 0.15')).toBeInTheDocument()
  })
})

describe('EventGlass', () => {
  it('types the moment text progressively', () => {
    const m = { tick: 8, label: 'Ivan to Clara', text: 'abcdefghij' }
    const { rerender } = render(<EventGlass moment={m} t={8.7} done={false} />)
    expect(screen.getByText('Tick 8, Ivan to Clara')).toBeInTheDocument()
    expect(screen.getByTestId('glass-text').textContent).toBe('abcde')
    rerender(<EventGlass moment={m} t={10} done={false} />)
    expect(screen.getByTestId('glass-text').textContent).toBe('abcdefghij')
  })
  it('shows the verdict when done', () => {
    render(<EventGlass moment={null} t={20} done verdict="Leans toward selling." />)
    expect(screen.getByTestId('glass-text').textContent).toBe('Leans toward selling.')
  })
})

describe('StatusStrip', () => {
  it('rolls the odometer to the current tick and labels status', () => {
    render(<StatusStrip t={16.4} totalTicks={20} status="recording" nAgents={15} nCamps={5} />)
    const strips = screen.getAllByTestId('odo-strip')
    expect(strips[0].style.transform).toBe('translateY(-42px)')
    expect(strips[1].style.transform).toBe('translateY(-252px)')
    expect(screen.getByText('Recording')).toBeInTheDocument()
    expect(screen.getByText('15 agents in 5 camps')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/panels.test.jsx`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement**

`Readout.jsx`:

```jsx
import { stanceLabel } from './model.js'

const change = (d, cap) => (Math.abs(d) < 0.005 ? (cap ? 'Unchanged' : 'unchanged') : `${cap ? (d < 0 ? 'Down' : 'Up') : (d < 0 ? 'down' : 'up')} ${Math.abs(d).toFixed(2)}`)

export default function Readout({ room, roomStart, spectrum, camps, campValues, campStarts, highlightCampId }) {
  return (
    <div>
      <div style={{ fontSize: 14, color: 'var(--dim)' }}>The room</div>
      <div style={{ fontSize: 76, fontWeight: 500, letterSpacing: -2, lineHeight: 1.05, color: 'var(--accent)' }}>{room.toFixed(2)}</div>
      <div style={{ fontSize: 19, fontWeight: 500 }}>{stanceLabel(room, spectrum)}</div>
      <div style={{ fontSize: 14, color: 'var(--dim)', marginTop: 4 }}>{`${change(room - roomStart, true)} since tick 1`}</div>
      <div style={{ borderTop: '1px solid var(--line)', margin: '18px 0 8px' }} />
      {camps.map(c => {
        const hot = c.id === highlightCampId
        return (
          <div key={c.id} style={{ display: 'grid', gridTemplateColumns: '1fr auto', padding: '8px 0' }}>
            <span data-hot={String(hot)} style={{ fontSize: 16, fontWeight: 500, color: hot ? 'var(--accent)' : 'var(--ink)' }}>{c.name}</span>
            <span style={{ fontSize: 20, fontWeight: 500, gridRow: 'span 2', alignSelf: 'center' }}>{campValues[c.id].toFixed(2)}</span>
            <span style={{ fontSize: 13, color: 'var(--dim)' }}>{change(campValues[c.id] - campStarts[c.id], false)}</span>
          </div>
        )
      })}
    </div>
  )
}
```

`EventGlass.jsx`:

```jsx
export default function EventGlass({ moment, t, done, verdict }) {
  let title, text, typing = false
  if (done && verdict) { title = 'Run complete'; text = verdict }
  else if (moment) {
    title = `Tick ${moment.tick}, ${moment.label}`
    const f = Math.max(0, Math.min(1, (t - moment.tick) / 1.4))
    text = moment.text.slice(0, Math.floor(moment.text.length * f))
    typing = f < 1
  } else { title = `Tick ${Math.floor(t)}`; text = 'Listening to the room.' }
  return (
    <div className="rec-glass" aria-live="polite">
      <div className="t">{title}</div>
      <div className="m"><span data-testid="glass-text">{text}</span>{(typing || !done) && <span className="rec-cursor" aria-hidden="true" />}</div>
    </div>
  )
}
```

`StatusStrip.jsx`:

```jsx
const DIGITS = [...Array(10).keys()]

export default function StatusStrip({ t, totalTicks, status, nAgents, nCamps, runLabel }) {
  const dg = String(Math.min(99, Math.floor(t))).padStart(2, '0')
  const legend = (
    <span><b style={{ color: 'var(--accent)' }}>Accent pen</b> the whole room. <b>Dark pens</b> each camp’s average. <b>Faint lines</b> individual agents. Marks along the top are moments that moved the room.</span>
  )
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 32, padding: '0 56px', color: 'var(--dim)', fontSize: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span>Tick</span>
        {[0, 1].map(i => (
          <div key={i} className="rec-win"><div className="rec-strip" data-testid="odo-strip" style={{ transform: `translateY(${-42 * +dg[i]}px)` }}>{DIGITS.map(d => <div key={d}>{d}</div>)}</div></div>
        ))}
        <span>of {totalTicks}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <i className={`rec-lamp ${status === 'recording' ? 'on' : ''}`} aria-hidden="true" />
        <span>{status === 'recording' ? 'Recording' : status === 'paused' ? 'Paused' : 'Complete'}</span>
      </div>
      <span>{nAgents} agents in {nCamps} camps{runLabel ? `. ${runLabel}` : ''}</span>
      <span style={{ marginLeft: 'auto', maxWidth: 640, fontSize: 13, lineHeight: 1.5 }}>{legend}</span>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

Run: `cd src/ui && npx vitest run src/recorder/panels.test.jsx`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/recorder/Readout.jsx src/ui/src/recorder/EventGlass.jsx src/ui/src/recorder/StatusStrip.jsx src/ui/src/recorder/panels.test.jsx
git commit -m "feat(ui): recorder readout, event glass, status strip"
```

---

### Task 5: Stream client extracted from InputBar

**Files:**
- Create: `src/ui/src/api/streams.js`
- Modify: `src/ui/src/components/InputBar.jsx` (use `streamSSE` in the four handlers)
- Test: `src/ui/src/api/streams.test.js`

**Interfaces:**
- Produces: `async function streamSSE(path: string, body: object, onEvent: (event) => void, { signal } = {}) -> Promise<void>`; `export const ENDPOINTS = { consult: '/api/simulate/stream', oracle: '/api/oracle/stream', ensemble: '/api/ensemble/stream', backtest: '/api/backtest/stream' }`. Throws `Error(detail)` on non-2xx (uses JSON `detail` when present, so the Jev screening 422 message reaches the UI).

- [ ] **Step 1: Write the failing test**

```js
import { describe, it, expect, vi } from 'vitest'
import { streamSSE } from './streams.js'

function body(chunks) {
  const enc = new TextEncoder()
  let i = 0
  return { getReader: () => ({ read: async () => (i < chunks.length ? { done: false, value: enc.encode(chunks[i++]) } : { done: true }) }) }
}

describe('streamSSE', () => {
  it('parses events split across chunks', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, body: body(['data: {"type":"thi', 'nking"}\n\ndata: {"type":"done","data":1}\n\n']) })
    const seen = []
    await streamSSE('/x', { prompt: 'q' }, e => seen.push(e))
    expect(seen).toEqual([{ type: 'thinking' }, { type: 'done', data: 1 }])
    expect(fetch).toHaveBeenCalledWith('/x', expect.objectContaining({ method: 'POST' }))
  })
  it('throws the server detail on error status', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: 'Describe a decision.' }) })
    await expect(streamSSE('/x', {}, () => {})).rejects.toThrow('Describe a decision.')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/api/streams.test.js`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `streams.js`**

```js
export const ENDPOINTS = {
  consult: '/api/simulate/stream',
  oracle: '/api/oracle/stream',
  ensemble: '/api/ensemble/stream',
  backtest: '/api/backtest/stream',
}

export async function streamSSE(path, body, onEvent, { signal } = {}) {
  const resp = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`
    try { const j = await resp.json(); if (typeof j.detail === 'string') detail = j.detail } catch { /* keep default */ }
    throw new Error(detail)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = frame.split('\n').find(l => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}
```

- [ ] **Step 4: Use it in InputBar**

In each of `handleConsult`, `handleOracle`, `handleEnsemble`, `handleBacktest` in `src/ui/src/components/InputBar.jsx`, replace the `fetch(...)` + `getReader()` + manual parsing loop with a single `await streamSSE(ENDPOINTS.<mode>, <same body object>, event => { <the existing per-event handling> })`, keeping each handler's existing special cases (oracle/ensemble `done` routed to `onOracleResult` / `onEnsembleResult`, backtest's `backtest` event to `onBacktestResult`). Keep the existing `try/catch/finally` that toggles `setIsLoading`.

Run: `cd src/ui && npx vitest run` — all pass. Then manual check: `npm run dev`, click ▶ demo (unaffected) and, with the backend running, one Consult run streams as before.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/api/streams.js src/ui/src/api/streams.test.js src/ui/src/components/InputBar.jsx
git commit -m "refactor(ui): extract SSE stream client"
```

---

### Task 6: Recorder assembly, App wiring, demo influence events

**Files:**
- Create: `src/ui/src/recorder/Recorder.jsx`
- Create: `src/ui/src/recorder/RecorderHeader.jsx`
- Modify: `src/ui/src/App.jsx` (stream state + routing)
- Modify: `src/ui/src/simulation/demo.js` (emit `influence`, add `camp` to demo agents)
- Test: `src/ui/src/recorder/Recorder.test.jsx`, `src/ui/src/simulation/demo.test.js`

**Interfaces:**
- Consumes: Tasks 1–5
- Produces:
  - `<Recorder scenario: { title, stance_spectrum, tick_count, agents }, ticks: TickRecord[], influence: {tick, edges}[], extraMoments?: Moment[], done: object | null, runLabel?: string, faintRooms?: number[][], target?: number | null, onReadAnalysis: () => void />`
  - `<RecorderHeader prompt, setPrompt, mode, setMode, preset, setPreset, onRun, onDemo, isLoading, error />` — modes `consult | oracle | ensemble | backtest`; size presets move into a popover opened by a "Size" button
  - `App` state: `live = { scenario, ticks, influence, runCompletes, runs, done, backtest }`

- [ ] **Step 1: Write the failing tests**

`Recorder.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Recorder from './Recorder.jsx'

window.matchMedia = q => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} })

const scenario = {
  title: 'T', tick_count: 2, stance_spectrum: ['Strong sell', 'Leaning sell', 'Neutral', 'Leaning buy', 'Strong buy'],
  agents: [{ id: 'a', name: 'Ann', camp: 'Retail', initial_stance: 0.4 }, { id: 'b', name: 'Ben', camp: 'Institutional', initial_stance: 0.6 }],
}
const ticks = [{ tick: 1, events: [{ agent_id: 'a', stance: 0.3 }, { agent_id: 'b', stance: 0.6 }] }]

describe('Recorder', () => {
  it('renders pens per camp and the readout', () => {
    render(<Recorder scenario={scenario} ticks={ticks} influence={[]} done={null} onReadAnalysis={() => {}} />)
    expect(screen.getByTestId('pen-Retail')).toBeInTheDocument()
    expect(screen.getByTestId('pen-Institutional')).toBeInTheDocument()
    expect(screen.getByText('2 agents in 2 camps')).toBeInTheDocument()
  })
  it('shows the verdict card with an analysis link when done', () => {
    const onRead = vi.fn()
    const done = { decision_summary: { verdict: 'Leans toward selling.', verdict_label: 'Leaning sell', confidence: 'moderate' }, quality: { usage: { cost_usd: 0.0123 } } }
    render(<Recorder scenario={{ ...scenario, tick_count: 1 }} ticks={ticks} influence={[]} done={done} onReadAnalysis={onRead} />)
    fireEvent.click(screen.getByRole('button', { name: 'Read the analysis' }))
    expect(onRead).toHaveBeenCalled()
    expect(screen.getByText('$0.012')).toBeInTheDocument()
  })
})
```

Append to `src/ui/src/simulation/demo.test.js`:

```js
import { vi } from 'vitest'
import { startDemoStream } from './demo.js'

describe('demo stream', () => {
  it('emits an influence event after every tick and camps on agents', () => {
    vi.useFakeTimers()
    const events = []
    startDemoStream(e => events.push(e))
    vi.runAllTimers()
    vi.useRealTimers()
    const scenario = events.find(e => e.type === 'scenario')
    expect(scenario.data.agents.every(a => a.camp)).toBe(true)
    const ticks = events.filter(e => e.type === 'tick').length
    expect(events.filter(e => e.type === 'influence').length).toBe(ticks)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/Recorder.test.jsx src/simulation/demo.test.js`
Expected: FAIL (Recorder missing; demo emits no influence events).

- [ ] **Step 3: Implement `Recorder.jsx`**

```jsx
import { useMemo } from 'react'
import './recorder.css'
import ChartPaper from './ChartPaper.jsx'
import EventGlass from './EventGlass.jsx'
import Readout from './Readout.jsx'
import StatusStrip from './StatusStrip.jsx'
import { activeMoment, buildSeries, campOf, campSeries, groupCamps, momentsFromInfluence, valueAt } from './model.js'
import { useRecorderClock } from './useRecorderClock.js'

export default function Recorder({ scenario, ticks, influence, extraMoments = [], done, runLabel, faintRooms = [], target = null, onReadAnalysis }) {
  const agents = scenario.agents
  const camps = useMemo(() => groupCamps(agents), [agents])
  const byId = useMemo(() => Object.fromEntries(agents.map(a => [a.id, a])), [agents])
  const { byAgent, room } = useMemo(() => buildSeries(agents, ticks), [agents, ticks])
  const cs = useMemo(() => campSeries(byAgent, camps), [byAgent, camps])
  const moments = useMemo(() => [...momentsFromInfluence(influence, byId), ...extraMoments].sort((a, b) => a.tick - b.tick), [influence, byId, extraMoments])

  const t = useRecorderClock(ticks.length)
  const complete = !!done && t >= ticks.length
  const moment = activeMoment(moments, t)
  const hotCamp = moment?.targetId ? campOf(byId[moment.targetId] || {}) : undefined
  const summary = done?.decision_summary
  const cost = done?.quality?.usage?.cost_usd

  return (
    <div className="rec-body" style={{ display: 'contents' }}>
      <div className="rec-main">
        <div className="rec-well">
          <ChartPaper camps={camps} agentSeries={byAgent} campSeries={cs} roomSeries={room} moments={moments}
            t={t} totalTicks={scenario.tick_count} target={target} faintRooms={faintRooms} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
          {complete && summary ? (
            <div className="rec-verdict" style={{ background: 'var(--rockerOn)', borderRadius: 14, padding: 18 }}>
              <div style={{ fontSize: 13, color: 'var(--dim)' }}>Verdict</div>
              <div style={{ fontSize: 22, fontWeight: 600, margin: '6px 0' }}>{summary.verdict_label}</div>
              <div style={{ fontSize: 15, lineHeight: 1.5 }}>{summary.verdict}</div>
              <div style={{ fontSize: 13, color: 'var(--dim)', marginTop: 10 }}>
                Confidence {summary.confidence}{cost != null ? <>. Cost <span>{`$${cost.toFixed(3)}`}</span></> : null}
              </div>
              <button type="button" onClick={onReadAnalysis} style={{ marginTop: 14, padding: '9px 14px', borderRadius: 9, border: 0, background: 'var(--accent)', color: '#141517', fontWeight: 600, cursor: 'pointer' }}>
                Read the analysis
              </button>
            </div>
          ) : (
            <Readout room={valueAt(room, t)} roomStart={room[0]} spectrum={scenario.stance_spectrum} camps={camps}
              campValues={Object.fromEntries(camps.map(c => [c.id, valueAt(cs[c.id], t)]))}
              campStarts={Object.fromEntries(camps.map(c => [c.id, cs[c.id][0]]))} highlightCampId={hotCamp} />
          )}
          <div style={{ marginTop: 'auto' }}>
            <EventGlass moment={moment} t={t} done={complete} verdict={summary?.verdict} />
          </div>
        </div>
      </div>
      <StatusStrip t={t} totalTicks={scenario.tick_count} status={complete ? 'complete' : 'recording'}
        nAgents={agents.length} nCamps={camps.length} runLabel={runLabel} />
    </div>
  )
}
```

The verdict card slides in: add to `recorder.css`

```css
.rec-verdict { animation:rec-slide .5s cubic-bezier(.2,.8,.2,1); }
@keyframes rec-slide { from { opacity:0; transform:translateY(12px); } }
@media (prefers-reduced-motion: reduce) { .rec-verdict { animation:none; } }
```

- [ ] **Step 4: Implement `RecorderHeader.jsx`**

```jsx
import { useState } from 'react'

const MODES = [['consult', 'Consult'], ['oracle', 'Oracle loop'], ['ensemble', 'Ensemble'], ['backtest', 'Backtest']]
const PRESETS = [['auto', 'Auto', 'Pythia picks the size'], ['fast', 'Fast', '4 agents, 8 ticks'], ['balanced', 'Balanced', '6 agents, 15 ticks'], ['deep', 'Deep', '10 agents, 25 ticks']]

export default function RecorderHeader({ prompt, setPrompt, mode, setMode, preset, setPreset, onRun, onDemo, isLoading, error }) {
  const [sizeOpen, setSizeOpen] = useState(false)
  return (
    <header style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '0 40px', position: 'relative' }}>
      <span style={{ fontSize: 22, fontWeight: 600 }}>Pythia</span>
      <form onSubmit={e => { e.preventDefault(); onRun() }} style={{ flex: 1, display: 'flex', gap: 10 }}>
        <label htmlFor="rec-q" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>Decision to simulate</label>
        <input id="rec-q" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Should we raise a Series A or stay bootstrapped?"
          style={{ flex: 1, height: 42, padding: '0 16px', borderRadius: 10, border: 0, background: 'var(--field)', color: 'var(--ink)', font: 'inherit', fontSize: 16 }} />
        <button type="submit" disabled={isLoading || !prompt.trim()} style={{ padding: '0 16px', borderRadius: 10, border: 0, background: 'var(--accent)', color: '#141517', fontWeight: 600, cursor: 'pointer' }}>Run</button>
      </form>
      <div role="radiogroup" aria-label="Mode" style={{ display: 'flex', padding: 3, borderRadius: 11, background: 'var(--rocker)' }}>
        {MODES.map(([id, label]) => (
          <button key={id} role="radio" aria-checked={mode === id} onClick={() => setMode(id)} type="button"
            style={{ padding: '8px 14px', borderRadius: 8, border: 0, font: 'inherit', fontSize: 14, fontWeight: 500, cursor: 'pointer',
              background: mode === id ? 'var(--rockerOn)' : 'transparent', color: mode === id ? 'var(--ink)' : 'var(--dim)' }}>{label}</button>
        ))}
      </div>
      <button type="button" onClick={() => setSizeOpen(o => !o)} aria-expanded={sizeOpen} style={{ background: 'none', border: 0, color: 'var(--dim)', font: 'inherit', cursor: 'pointer' }}>Size</button>
      <button type="button" onClick={onDemo} style={{ background: 'none', border: 0, color: 'var(--dim)', font: 'inherit', cursor: 'pointer' }}>Demo</button>
      {sizeOpen && (
        <div role="dialog" aria-label="Simulation size" style={{ position: 'absolute', right: 110, top: 64, zIndex: 10, background: 'var(--housing)', borderRadius: 12, padding: 8, boxShadow: '0 12px 30px rgba(0,0,0,.35)' }}>
          {PRESETS.map(([id, label, desc]) => (
            <button key={id} type="button" onClick={() => { setPreset(id); setSizeOpen(false) }}
              style={{ display: 'grid', textAlign: 'left', width: 220, padding: '8px 10px', borderRadius: 8, border: 0, cursor: 'pointer', font: 'inherit',
                background: preset === id ? 'var(--rockerOn)' : 'transparent', color: 'var(--ink)' }}>
              <span style={{ fontWeight: 500 }}>{label}</span><span style={{ fontSize: 13, color: 'var(--dim)' }}>{desc}</span>
            </button>
          ))}
        </div>
      )}
      {error && <div role="alert" style={{ position: 'absolute', left: 140, top: 66, fontSize: 13, color: 'var(--accent)' }}>{error}</div>}
    </header>
  )
}
```

- [ ] **Step 5: Demo emits influence and camps**

In `src/ui/src/simulation/demo.js`:
1. Add a `camp` field to each `DEMO_AGENTS` entry equal to its `role` (for example `camp: 'Retail Investor'`).
2. In `startDemoStream`, where each tick is scheduled with `after(2100 + i * 80, () => onEvent({ type: 'tick', data: tick }))`, schedule right after it:

```js
    after(2100 + i * 80 + 1, () => onEvent({
      type: 'influence',
      data: { tick: tick.tick, edges: (doneResult.influence_graph?.edges || []).filter(e => e.tick === tick.tick) },
    }))
```

(`doneResult` is already built at the top of `startDemoStream`, and the `scenario` event spreads `DEMO_AGENTS`, so the new `camp` fields reach the recorder without further changes.)

- [ ] **Step 6: Wire App**

In `src/ui/src/App.jsx`:
1. Add state: `const [live, setLive] = useState(null)` and `const [view, setView] = useState('live')`.
2. In `handleStreamEvent`, alongside the existing branches:
   - `thinking`: `setLive(null); setView('live')`
   - `scenario`: `setLive({ scenario: event.data, ticks: [], influence: [], runCompletes: [], runs: [], done: null, backtest: null })`
   - `tick`: `setLive(l => l && { ...l, ticks: [...l.ticks, event.data] })`
   - `influence`: `setLive(l => l && { ...l, influence: [...l.influence, event.data] })`
   - `run_start`: `setLive(l => l && (event.data.run_number > 1 ? { ...l, runs: [...l.runs, l.ticks], ticks: [], influence: [] } : l))`
   - `run_complete`: `setLive(l => l && { ...l, runCompletes: [...l.runCompletes, event.data] })`
   - `backtest`: `setLive(l => l && { ...l, backtest: event.data })`
   - `done`: `setLive(l => l && { ...l, done: event.data })`
3. Render: when `live?.scenario` exists and `view === 'live'`, render inside `<div className="rec">`:

```jsx
<div className="rec">
  <RecorderHeader {...headerProps} />
  <Recorder
    scenario={live.scenario}
    ticks={live.ticks}
    influence={live.influence}
    done={live.done}
    onReadAnalysis={() => setView('analysis')}
  />
</div>
```

   Lift `prompt`, `mode` (default `'consult'`), and `preset` (default `'auto'`) into `App` state, add `const [runError, setRunError] = useState(null)`, and add:

```jsx
function buildRequestBody(mode, prompt, preset) {
  const body = { prompt: prompt.trim() }
  if (preset !== 'auto') body.preset = preset
  if (mode === 'oracle') body.max_runs = 5
  if (mode === 'ensemble') body.ensemble_size = 3
  return body
}

async function run() {
  if (!prompt.trim() || isLoading) return
  setIsLoading(true)
  setRunError(null)
  try {
    await streamSSE(ENDPOINTS[mode], buildRequestBody(mode, prompt, preset), handleStreamEvent)
  } catch (err) {
    setRunError(err.message)
  } finally {
    setIsLoading(false)
  }
}

const headerProps = {
  prompt, setPrompt, mode, setMode, preset, setPreset,
  onRun: run, onDemo: () => startDemoStream(handleStreamEvent),
  isLoading, error: runError,
}
```

   Backtest's ground-truth fields and document upload are added to the header in Task 9; until then, use the old `InputBar` for those two flows. The old `InputBar` path stays in place for the landing screen and non-live results until Task 10.

- [ ] **Step 7: Run tests and look at it**

Run: `cd src/ui && npx vitest run` — all pass.

Run `npm run dev`, click Demo: the recorder shows paper scrolling, camp pens, event marks, typing glass, odometer, and the verdict card at the end. Check at a narrow window (≤ 900px) that the readout stacks under the paper.

- [ ] **Step 8: Commit**

```bash
git add src/ui/src/recorder src/ui/src/App.jsx src/ui/src/simulation/demo.js src/ui/src/simulation/demo.test.js
git commit -m "feat(ui): chart-recorder live view wired to consult stream and demo"
```

---

### Task 7: Analysis page

**Files:**
- Create: `src/ui/src/analysis/AnalysisPage.jsx`, `CampsChart.jsx`, `SmallMultiples.jsx`, `analysis.css`
- Modify: `src/ui/src/App.jsx` (`view === 'analysis'`)
- Test: `src/ui/src/analysis/AnalysisPage.test.jsx`

**Interfaces:**
- Consumes: `groupCamps`, `buildSeries`, `campSeries`, `stanceLabel` (Task 1); `done` payload (`RunResultWithInsights` JSON: `agents`, `ticks`, `scenario.stance_spectrum`, `decision_summary`, `methodology`, `quality`)
- Produces: `<AnalysisPage result onBack />`

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AnalysisPage from './AnalysisPage.jsx'

const result = {
  scenario: { title: 'Fed decision', input: 'Should we?', stance_spectrum: ['Strong sell', 'Leaning sell', 'Neutral', 'Leaning buy', 'Strong buy'] },
  agents: [{ id: 'a', name: 'Ann', camp: 'Retail', initial_stance: 0.4 }, { id: 'b', name: 'Ben', camp: 'Institutional', initial_stance: 0.6 }],
  ticks: [{ tick: 1, events: [{ agent_id: 'a', stance: 0.2 }, { agent_id: 'b', stance: 0.58 }] }],
  decision_summary: {
    verdict: 'The panel leans toward selling.', verdict_label: 'Leaning sell', confidence: 'moderate', confidence_rationale: 'Spread is wide.',
    arguments_for: [{ agent_name: 'Ben', agent_role: 'Institutional', position: 'Hold', reasoning: 'Priced in.' }],
    arguments_against: [{ agent_name: 'Ann', agent_role: 'Retail', position: 'Sell', reasoning: 'Too risky.' }],
    key_risk: 'Surprise guidance.', what_could_change: 'A dovish statement.', actionable_takeaways: ['Hedge.'],
    influence_narrative: 'Ben held.', herd_moments: [],
  },
  quality: { parse_failures: 0, usage: { cost_usd: 0.0123, calls: 20 } },
}

describe('AnalysisPage', () => {
  it('leads with the verdict and shows camps and arguments', () => {
    render(<AnalysisPage result={result} onBack={() => {}} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The panel leans toward selling.')
    expect(screen.getByTestId('camp-row-Retail')).toHaveTextContent('down 0.20')
    expect(screen.getByText('Priced in.')).toBeInTheDocument()
    expect(screen.getByText('Too risky.')).toBeInTheDocument()
    expect(screen.getByText(/\$0\.012/)).toBeInTheDocument()
  })
  it('goes back to the recorder', () => {
    const onBack = vi.fn()
    render(<AnalysisPage result={result} onBack={onBack} />)
    fireEvent.click(screen.getByRole('button', { name: 'Back to the recorder' }))
    expect(onBack).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/analysis/AnalysisPage.test.jsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`analysis.css` (journalism layout in the recorder's type and palette, on paper):

```css
.ana { --paper:#F4F4F0; --ink:#1B1D20; --dim:#5E6166; --rule:#CBD1CA; --accent:#C9432A;
  font-family:'Archivo',system-ui,sans-serif; font-variant-numeric:tabular-nums; background:var(--paper); color:var(--ink); min-height:100dvh; }
.ana-wrap { max-width:1120px; margin:0 auto; padding:40px 24px 80px; }
.ana h1 { font-size:40px; line-height:1.15; font-weight:600; letter-spacing:-.6px; margin:12px 0; max-width:30ch; }
.ana h2 { font-size:20px; font-weight:600; margin:40px 0 12px; }
.ana .sub { font-size:17px; color:var(--dim); }
.ana .cols { display:grid; grid-template-columns:1fr 1fr; gap:32px; }
.ana .arg { border-top:1px solid var(--rule); padding:12px 0; }
.ana .arg b { display:block; }
.ana .meta { font-size:14px; color:var(--dim); }
@media (max-width: 760px) { .ana .cols { grid-template-columns:1fr; } .ana h1 { font-size:30px; } }
```

`CampsChart.jsx`:

```jsx
const X = v => 160 + v * 820

export default function CampsChart({ camps, byAgent, campSeriesById }) {
  const rowH = 64
  return (
    <svg viewBox={`0 0 1100 ${camps.length * rowH + 40}`} role="img" aria-label="Where each camp ended, with every agent as a dot">
      {[0.2, 0.4, 0.6, 0.8].map(v => <line key={v} x1={X(v)} x2={X(v)} y1={0} y2={camps.length * rowH} stroke="#E3E6E1" strokeDasharray="2 5" />)}
      {camps.map((c, i) => {
        const y = i * rowH + rowH / 2
        const s = campSeriesById[c.id]
        const end = s[s.length - 1], d = end - s[0]
        return (
          <g key={c.id} data-testid={`camp-row-${c.id}`}>
            <text x={0} y={y + 5} fontSize={16} fontWeight={600} fill="currentColor">{c.name}</text>
            {c.agentIds.map((id, j) => { const v = byAgent[id][byAgent[id].length - 1]; return <circle key={id} cx={X(v)} cy={y + ((j % 3) - 1) * 9} r={6} fill="#1B1D20" fillOpacity={0.8} /> })}
            <line x1={X(end)} x2={X(end)} y1={y - 22} y2={y + 22} stroke="#1B1D20" strokeWidth={2} />
            <text x={1100} y={y} textAnchor="end" fontSize={16} fontWeight={600} fill="currentColor">{end.toFixed(2)}</text>
            <text x={1100} y={y + 18} textAnchor="end" fontSize={13} fill="#5E6166">{Math.abs(d) < 0.005 ? 'no change' : `${d < 0 ? 'down' : 'up'} ${Math.abs(d).toFixed(2)}`}</text>
          </g>
        )
      })}
    </svg>
  )
}
```

`SmallMultiples.jsx`:

```jsx
export default function SmallMultiples({ camps, byAgent, campSeriesById, room }) {
  const w = 320, h = 160
  const path = s => s.map((v, i) => `${i ? 'L' : 'M'}${((i / Math.max(1, s.length - 1)) * (w - 40)).toFixed(1)} ${(20 + (1 - v) * (h - 40)).toFixed(1)}`).join('')
  const panels = [...camps.map(c => ({ id: c.id, name: c.name, lines: c.agentIds.map(id => byAgent[id]), main: campSeriesById[c.id], accent: false })),
    { id: 'room', name: 'The whole room', lines: camps.map(c => campSeriesById[c.id]), main: room, accent: true }]
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
      {panels.map(p => (
        <figure key={p.id} style={{ margin: 0 }}>
          <figcaption style={{ fontWeight: 600, color: p.accent ? 'var(--accent)' : 'inherit' }}>{p.name}</figcaption>
          <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${p.name} over time`}>
            <line x1={0} x2={w - 40} y1={20 + 0.5 * (h - 40)} y2={20 + 0.5 * (h - 40)} stroke="#D9D9D5" strokeDasharray="2 4" />
            {p.lines.map((s, i) => <path key={i} d={path(s)} fill="none" stroke="#B4B7BD" strokeWidth={1} />)}
            <path d={path(p.main)} fill="none" stroke={p.accent ? 'var(--accent)' : '#1B1D20'} strokeWidth={2.4} />
          </svg>
        </figure>
      ))}
    </div>
  )
}
```

`AnalysisPage.jsx`:

```jsx
import { useMemo } from 'react'
import './analysis.css'
import CampsChart from './CampsChart.jsx'
import SmallMultiples from './SmallMultiples.jsx'
import { buildSeries, campSeries, groupCamps } from '../recorder/model.js'

function Args({ title, items }) {
  return (
    <div>
      <h2>{title}</h2>
      {items.map((a, i) => (
        <div key={i} className="arg"><b>{a.agent_name}, {a.agent_role}</b><span className="meta">{a.position}</span><p>{a.reasoning}</p></div>
      ))}
    </div>
  )
}

export default function AnalysisPage({ result, onBack }) {
  const camps = useMemo(() => groupCamps(result.agents), [result.agents])
  const { byAgent, room } = useMemo(() => buildSeries(result.agents, result.ticks), [result.agents, result.ticks])
  const cs = useMemo(() => campSeries(byAgent, camps), [byAgent, camps])
  const s = result.decision_summary || {}
  const usage = result.quality?.usage || {}
  return (
    <div className="ana">
      <div className="ana-wrap">
        <button type="button" onClick={onBack} style={{ background: 'none', border: 0, font: 'inherit', color: 'var(--dim)', cursor: 'pointer', padding: 0 }}>Back to the recorder</button>
        <p className="sub" style={{ marginTop: 24 }}>{result.scenario.input}</p>
        <h1>{s.verdict}</h1>
        <p className="sub">{s.verdict_label}. Confidence {s.confidence}. {s.confidence_rationale}</p>

        <h2>Where each camp ended</h2>
        <CampsChart camps={camps} byAgent={byAgent} campSeriesById={cs} />

        <h2>How the room moved</h2>
        <SmallMultiples camps={camps} byAgent={byAgent} campSeriesById={cs} room={room} />

        <div className="cols">
          <Args title="The case for" items={s.arguments_for || []} />
          <Args title="The case against" items={s.arguments_against || []} />
        </div>

        <div className="cols">
          <div><h2>Key risk</h2><p>{s.key_risk}</p></div>
          <div><h2>What could change the outcome</h2><p>{s.what_could_change}</p></div>
        </div>

        {s.actionable_takeaways?.length > 0 && (<><h2>What to do next</h2><ul>{s.actionable_takeaways.map((t, i) => <li key={i}>{t}</li>)}</ul></>)}
        {s.influence_narrative && (<><h2>Who moved whom</h2><p>{s.influence_narrative}</p></>)}

        <h2>How this was computed</h2>
        <p className="meta">
          {result.agents.length} agents in {camps.length} camps, {result.ticks.length} ticks.
          {usage.calls != null && ` ${usage.calls} model calls.`}
          {usage.cost_usd != null && ` Cost $${usage.cost_usd.toFixed(3)}.`}
          {result.quality?.parse_failures ? ` ${result.quality.parse_failures} agent turns could not be read and were held at their previous stance.` : ''}
        </p>
      </div>
    </div>
  )
}
```

In `App.jsx`, when `view === 'analysis' && live?.done`, render `<AnalysisPage result={live.done} onBack={() => setView('live')} />`.

- [ ] **Step 4: Run tests**

Run: `cd src/ui && npx vitest run`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/analysis src/ui/src/App.jsx
git commit -m "feat(ui): journalism-style analysis page"
```

---

### Task 8: Oracle loop, ensemble, and backtest in the recorder

**Files:**
- Modify: `src/ui/src/App.jsx` (pass mode-specific props to `Recorder`)
- Modify: `src/ui/src/components/InputBar.jsx` only if it still owns the oracle/ensemble `done` routing
- Test: `src/ui/src/recorder/modes.test.jsx`

**Interfaces:**
- Consumes: `reflectMoment` (Task 1); `live.runs`, `live.runCompletes`, `live.backtest` (Task 6)
- Produces: mapping from `live` + mode to `Recorder` props:
  - Oracle: `runLabel = "Run {n} of {max}"`, `extraMoments = [reflectMoment(lastRunComplete, byId, 0)]` when the new run has started
  - Ensemble: `faintRooms = live.runs.map(ticks => buildSeries(agents, ticks).room)`, `runLabel = "Run {n} of {max}"`
  - Backtest: `target = live.backtest?.actual_aggregate ?? null`

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect } from 'vitest'
import { recorderPropsFor } from '../App.jsx'

const scenario = { agents: [{ id: 'a', name: 'Ann', camp: 'R', initial_stance: 0.5 }], stance_spectrum: ['1', '2', '3', '4', '5'], tick_count: 2 }

describe('recorderPropsFor', () => {
  it('oracle: run label and a reflect moment for amended agents', () => {
    const live = { scenario, runs: [[{ tick: 1, events: [] }]], runCompletes: [{ run_number: 1, amended_agent_ids: ['a'] }], ticks: [], runStart: { run_number: 2, max_runs: 3 } }
    const p = recorderPropsFor('oracle', live)
    expect(p.runLabel).toBe('Run 2 of 3')
    expect(p.extraMoments[0].kind).toBe('reflect')
  })
  it('ensemble: faint room traces for finished runs', () => {
    const live = { scenario, runs: [[{ tick: 1, events: [{ agent_id: 'a', stance: 0.3 }] }]], runCompletes: [], ticks: [], runStart: { run_number: 2, max_runs: 5 } }
    const p = recorderPropsFor('ensemble', live)
    expect(p.faintRooms).toEqual([[0.5, 0.3]])
  })
  it('backtest: target line from the actual outcome', () => {
    expect(recorderPropsFor('backtest', { scenario, runs: [], runCompletes: [], ticks: [], backtest: { actual_aggregate: 0.3 } }).target).toBe(0.3)
  })
  it('consult: no extras', () => {
    expect(recorderPropsFor('consult', { scenario, runs: [], runCompletes: [], ticks: [] })).toEqual({ extraMoments: [], faintRooms: [], target: null, runLabel: undefined })
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/modes.test.jsx`
Expected: FAIL (`recorderPropsFor` not exported).

- [ ] **Step 3: Implement in `App.jsx`**

Also record `run_start` data: in the `run_start` branch set `runStart: event.data` on `live`.

```jsx
import { buildSeries, reflectMoment } from './recorder/model.js'

export function recorderPropsFor(mode, live) {
  const byId = Object.fromEntries(live.scenario.agents.map(a => [a.id, a]))
  const runLabel = live.runStart ? `Run ${live.runStart.run_number} of ${live.runStart.max_runs}` : undefined
  if (mode === 'oracle') {
    const last = live.runCompletes[live.runCompletes.length - 1]
    const m = last && live.runStart && live.runStart.run_number > last.run_number ? reflectMoment(last, byId, 0) : null
    return { extraMoments: m ? [m] : [], faintRooms: [], target: null, runLabel }
  }
  if (mode === 'ensemble') {
    return { extraMoments: [], faintRooms: live.runs.map(ticks => buildSeries(live.scenario.agents, ticks).room), target: null, runLabel }
  }
  if (mode === 'backtest') {
    return { extraMoments: [], faintRooms: [], target: live.backtest?.actual_aggregate ?? null, runLabel: undefined }
  }
  return { extraMoments: [], faintRooms: [], target: null, runLabel: undefined }
}
```

Spread `{...recorderPropsFor(mode, live)}` onto `<Recorder>`. The `done` payload differs per mode, so add and use this for the analysis page:

```jsx
export function analysisResultFor(mode, done) {
  if (!done) return null
  if (mode === 'oracle') {
    const last = done.runs[done.runs.length - 1].result
    return { ...last, decision_summary: done.decision_summary, influence_graph: done.influence_graph }
  }
  if (mode === 'ensemble') return done.primary_run || done.runs[0]
  return done
}
```

Render `<AnalysisPage result={analysisResultFor(mode, live.done)} ... />`, and pass `done={analysisResultFor(mode, live.done)}` to `<Recorder>` so its verdict card reads the same shape. Add a test case to `modes.test.jsx`:

```jsx
import { analysisResultFor } from '../App.jsx'

it('analysisResultFor unwraps oracle and ensemble payloads', () => {
  const oracle = { runs: [{ result: { run_id: 'r1' } }, { result: { run_id: 'r2' } }], decision_summary: { verdict: 'v' }, influence_graph: { edges: [] } }
  expect(analysisResultFor('oracle', oracle)).toEqual({ run_id: 'r2', decision_summary: { verdict: 'v' }, influence_graph: { edges: [] } })
  expect(analysisResultFor('ensemble', { primary_run: { run_id: 'p' }, runs: [] })).toEqual({ run_id: 'p' })
  expect(analysisResultFor('consult', { run_id: 'c' })).toEqual({ run_id: 'c' })
})
```

- [ ] **Step 4: Run tests and check each mode by hand**

Run: `cd src/ui && npx vitest run` — all pass.

With the backend running, run one small job per mode (Fast preset): oracle shows "Run 2 of N" and a reflect message after run 1; ensemble shows faint accent traces for finished runs; backtest shows the dashed "Actual outcome" line.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/App.jsx src/ui/src/recorder/modes.test.jsx
git commit -m "feat(ui): oracle, ensemble, and backtest in the recorder"
```

---

### Task 9: Landing state, run options, and error handling

**Files:**
- Create: `src/ui/src/recorder/EmptyRecorder.jsx`
- Create: `src/ui/src/recorder/RunOptions.jsx`
- Modify: `src/ui/src/recorder/RecorderHeader.jsx` (render `RunOptions` inside the Size popover), `src/ui/src/App.jsx` (`buildRequestBody` gains options)
- Test: `src/ui/src/recorder/EmptyRecorder.test.jsx`, `src/ui/src/recorder/RunOptions.test.jsx`

**Interfaces:**
- Produces:
  - `<EmptyRecorder examples: string[], onPick: (prompt) => void, thinking: boolean, title?: string />` — the recorder housing with blank paper; when idle it lists example questions; when `thinking` it shows the title and "Setting up the panel" in the glass.
  - `<RunOptions mode, options, setOptions />` with `options = { documentText: string | null, documentName: string | null, gtAggregate: number, gtConfidence: 'high' | 'moderate' | 'low' | 'polarized', gtNotes: string }`
  - `buildRequestBody(mode, prompt, preset, options)` adds `document_text`/`document_name` when present and `ground_truth_outcome: { aggregate_stance, confidence, notes }` when `mode === 'backtest'`

- [ ] **Step 1: Write the failing test**

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import EmptyRecorder from './EmptyRecorder.jsx'

describe('EmptyRecorder', () => {
  it('offers example questions when idle', () => {
    const onPick = vi.fn()
    render(<EmptyRecorder examples={['Should we raise?']} onPick={onPick} thinking={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Should we raise?' }))
    expect(onPick).toHaveBeenCalledWith('Should we raise?')
  })
  it('shows setup progress while thinking', () => {
    render(<EmptyRecorder examples={[]} onPick={() => {}} thinking title="Fed decision" />)
    expect(screen.getByText('Setting up the panel')).toBeInTheDocument()
    expect(screen.getByText('Fed decision')).toBeInTheDocument()
  })
})
```

`RunOptions.test.jsx`:

```jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import RunOptions from './RunOptions.jsx'
import { buildRequestBody } from '../App.jsx'

const base = { documentText: null, documentName: null, gtAggregate: 0.5, gtConfidence: 'moderate', gtNotes: '' }

describe('RunOptions', () => {
  it('shows ground-truth fields only for backtest', () => {
    const { rerender } = render(<RunOptions mode="consult" options={base} setOptions={() => {}} />)
    expect(screen.queryByLabelText('Actual outcome')).toBeNull()
    rerender(<RunOptions mode="backtest" options={base} setOptions={() => {}} />)
    expect(screen.getByLabelText('Actual outcome')).toBeInTheDocument()
  })
  it('updates the actual outcome', () => {
    const setOptions = vi.fn()
    render(<RunOptions mode="backtest" options={base} setOptions={setOptions} />)
    fireEvent.change(screen.getByLabelText('Actual outcome'), { target: { value: '0.3' } })
    expect(setOptions).toHaveBeenCalledWith({ ...base, gtAggregate: 0.3 })
  })
})

describe('buildRequestBody', () => {
  it('adds document and ground truth when relevant', () => {
    const opts = { ...base, documentText: 'doc', documentName: 'a.txt', gtAggregate: 0.3, gtNotes: 'n' }
    expect(buildRequestBody('backtest', ' q ', 'auto', opts)).toEqual({
      prompt: 'q', document_text: 'doc', document_name: 'a.txt',
      ground_truth_outcome: { aggregate_stance: 0.3, confidence: 'moderate', notes: 'n' },
    })
    expect(buildRequestBody('oracle', 'q', 'fast', base)).toEqual({ prompt: 'q', preset: 'fast', max_runs: 5 })
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd src/ui && npx vitest run src/recorder/EmptyRecorder.test.jsx src/recorder/RunOptions.test.jsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```jsx
import './recorder.css'

export default function EmptyRecorder({ examples, onPick, thinking, title }) {
  return (
    <div className="rec-main">
      <div className="rec-well" style={{ display: 'grid', placeItems: 'center', background: 'var(--paper)' }}>
        {thinking ? (
          <div style={{ color: 'var(--pen)', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 600 }}>{title || 'Reading your question'}</div>
          </div>
        ) : (
          <div style={{ color: 'var(--pen)', maxWidth: 560 }}>
            <div style={{ fontSize: 22, fontWeight: 600, marginBottom: 12 }}>Describe a decision. Watch the room respond.</div>
            {examples.map(q => (
              <button key={q} type="button" onClick={() => onPick(q)}
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '10px 0', border: 0, borderTop: '1px solid var(--grid2)', background: 'none', font: 'inherit', fontSize: 16, color: 'var(--pen)', cursor: 'pointer' }}>{q}</button>
            ))}
          </div>
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
        <div className="rec-glass"><div className="t">Status</div><div className="m">{thinking ? 'Setting up the panel' : 'Idle'}</div></div>
      </div>
    </div>
  )
}
```

`RunOptions.jsx`:

```jsx
const field = { width: '100%', padding: '6px 8px', borderRadius: 8, border: 0, background: 'var(--field)', color: 'var(--ink)', font: 'inherit' }

export default function RunOptions({ mode, options, setOptions }) {
  const set = patch => setOptions({ ...options, ...patch })
  async function onFile(e) {
    const f = e.target.files?.[0]
    if (!f) return
    set({ documentText: (await f.text()).slice(0, 50000), documentName: f.name.replace(/[\r\n]/g, ' ').slice(0, 100) })
  }
  return (
    <div style={{ display: 'grid', gap: 10, padding: '10px 10px 4px', borderTop: '1px solid var(--line)', marginTop: 6, width: 220 }}>
      <label style={{ fontSize: 13, color: 'var(--dim)' }}>
        Attach a document
        <input type="file" accept=".txt,.md" onChange={onFile} style={{ display: 'block', marginTop: 4, fontSize: 12 }} />
      </label>
      {options.documentName && (
        <button type="button" onClick={() => set({ documentText: null, documentName: null })} style={{ ...field, textAlign: 'left', cursor: 'pointer' }}>
          Remove {options.documentName}
        </button>
      )}
      {mode === 'backtest' && (
        <>
          <label style={{ fontSize: 13, color: 'var(--dim)' }}>
            Actual outcome
            <input type="number" min={0} max={1} step={0.01} value={options.gtAggregate} onChange={e => set({ gtAggregate: Number(e.target.value) })} style={field} />
          </label>
          <label style={{ fontSize: 13, color: 'var(--dim)' }}>
            Actual confidence
            <select value={options.gtConfidence} onChange={e => set({ gtConfidence: e.target.value })} style={field}>
              {['high', 'moderate', 'low', 'polarized'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 13, color: 'var(--dim)' }}>
            Notes
            <textarea maxLength={2000} value={options.gtNotes} onChange={e => set({ gtNotes: e.target.value })} rows={3} style={field} />
          </label>
        </>
      )}
    </div>
  )
}
```

In `RecorderHeader.jsx`, accept `options` and `setOptions` props and render `<RunOptions mode={mode} options={options} setOptions={setOptions} />` at the bottom of the Size popover. In `App.jsx`, add `const [options, setOptions] = useState({ documentText: null, documentName: null, gtAggregate: 0.5, gtConfidence: 'moderate', gtNotes: '' })`, pass both to the header, export `buildRequestBody`, and extend it:

```jsx
export function buildRequestBody(mode, prompt, preset, options) {
  const body = { prompt: prompt.trim() }
  if (preset !== 'auto') body.preset = preset
  if (options.documentText) { body.document_text = options.documentText; body.document_name = options.documentName }
  if (mode === 'oracle') body.max_runs = 5
  if (mode === 'ensemble') body.ensemble_size = 3
  if (mode === 'backtest') body.ground_truth_outcome = { aggregate_stance: options.gtAggregate, confidence: options.gtConfidence, notes: options.gtNotes }
  return body
}
```

Update the call in `run()` to `buildRequestBody(mode, prompt, preset, options)`.

In `App.jsx`, when there is no `live.scenario`, render `<div className="rec"><RecorderHeader .../><EmptyRecorder examples={SAMPLE_SCENARIOS} onPick={setPrompt} thinking={streamPhase === 'thinking'} title={streamTitle} /></div>`. Stream errors from `streamSSE` (including Jev's 422 message) go to `RecorderHeader`'s `error` prop.

- [ ] **Step 4: Run tests**

Run: `cd src/ui && npx vitest run` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/recorder/EmptyRecorder.jsx src/ui/src/recorder/EmptyRecorder.test.jsx src/ui/src/recorder/RunOptions.jsx src/ui/src/recorder/RunOptions.test.jsx src/ui/src/recorder/RecorderHeader.jsx src/ui/src/App.jsx
git commit -m "feat(ui): recorder landing, document and backtest options, error states"
```

---

### Task 10: Remove the old UI and verify

**Files:**
- Delete: `src/ui/src/components/{Header,Stage,Arena,Temple,AccuracyCurve,StanceGraph,InputBar,DecisionPanel,AgentDetail,OracleMethod}.jsx`, `src/ui/src/simulation/{crowdState,reducer,scenarios,useSimulation}.js` and their tests, `src/ui/public/compare.html`, `src/ui/prototype.html`
- Modify: `src/ui/src/App.jsx` (drop old imports and branches), `src/ui/src/index.css` (drop Playfair/Syne rules and old tokens), `src/ui/index.html` (fonts: Archivo only)
- Keep: `ErrorBoundary.jsx`, `demo.js`, `format.js`

- [ ] **Step 1: Confirm nothing still imports the old modules**

```bash
cd src/ui && grep -rn "components/\(Header\|Stage\|Arena\|Temple\|AccuracyCurve\|StanceGraph\|InputBar\|DecisionPanel\|AgentDetail\|OracleMethod\)\|simulation/\(crowdState\|reducer\|scenarios\|useSimulation\)" src
```

Expected: matches only in `App.jsx` imports that this task removes. Remove those imports and any branch that renders an old component.

- [ ] **Step 2: Delete**

```bash
cd src/ui
git rm src/components/{Header,Stage,Arena,Temple,AccuracyCurve,StanceGraph,InputBar,DecisionPanel,AgentDetail,OracleMethod}.jsx
git rm src/simulation/{crowdState,reducer,scenarios,useSimulation}.js src/simulation/{crowdState,reducer,scenarios}.test.js
git rm public/compare.html prototype.html
```

In `index.html`, set the fonts link to only `family=Archivo:ital,wght@0,400;0,500;0,600;1,400&display=swap`. In `src/index.css`, remove the `:root` gold/Playfair tokens and the Playfair descender rules; keep the reset and set `html, body, #root { height:100%; background:#141517; }`.

- [ ] **Step 3: Full verification**

```bash
cd src/ui && npx vitest run && npm run lint && npm run build
```

Expected: tests pass, lint clean, build succeeds.

In the browser (`npm run dev`):
1. Demo at default size: paper scrolls, pens move, marks stamp, glass types, odometer rolls, verdict card appears, "Read the analysis" opens the analysis page, "Back to the recorder" returns.
2. With the backend: Fast, Balanced, and Deep presets (4, 6, 10 agents), plus a 15-agent custom run: labels never overlap; faint lines stay faint.
3. Reduced motion on (OS setting or devtools emulation): no carriage easing, no blink or pulse; the paper advances per tick.
4. Narrow window (≤ 900px): readout stacks under the paper; no horizontal scroll.
5. Jev screening in primary (if enabled): a non-question prompt shows the friendly message under the header.

- [ ] **Step 4: Commit**

```bash
git add -A src/ui
git commit -m "feat(ui): retire the particle-arena UI in favour of the chart recorder"
```
