# Pythia Frontend Visualization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the `src/ui/prototype.html` visual mock into a production-grade React app with testable simulation state, proper component boundaries, and an identical visual result.

**Architecture:** A Vite + React SPA in `src/ui/`. Simulation state lives in a `useReducer`-based hook (`useSimulation`). Components are dumb — they receive props and fire callbacks. The Canvas particle system lives inside `Arena.jsx` via a `useEffect`. No external state library needed.

**Tech Stack:** Vite 6, React 19, Vitest, @testing-library/react, jsdom, CSS custom properties (no CSS-in-JS).

---

## File Map

```
src/ui/
├── index.html                         ← Vite entry, font link tags
├── package.json
├── vite.config.js
├── src/
│   ├── main.jsx                       ← React root mount
│   ├── App.jsx                        ← Root layout: Header + Stage/Arena/Temple + Footer
│   ├── index.css                      ← CSS tokens + resets + font import
│   ├── simulation/
│   │   ├── scenarios.js               ← Scenario data: protagonists, amendments
│   │   ├── scenarios.test.js
│   │   ├── reducer.js                 ← Pure sim state reducer
│   │   ├── reducer.test.js
│   │   └── useSimulation.js           ← Hook: wraps reducer + intervals/timeouts
│   └── components/
│       ├── Header.jsx                 ← Logo, scenario name, tick, restart btn, progress bar
│       ├── Stage.jsx                  ← Protagonist list + individual ProtagNode cards
│       ├── Arena.jsx                  ← Canvas wrapper + crowd label + particle loop
│       ├── Temple.jsx                 ← Idle + active retraining states
│       └── AccuracyCurve.jsx          ← SVG polyline accuracy chart
```

---

## Task 1: Scaffold Vite + React + Vitest

**Files:**
- Create: `src/ui/package.json`, `src/ui/vite.config.js`, `src/ui/index.html`
- Create: `src/ui/src/main.jsx`

- [ ] **Step 1: Scaffold the app**

```bash
cd /path/to/Pythia/src/ui
npm create vite@latest . -- --template react
```

When prompted about existing files, select "Ignore files and continue". Accept all defaults.

- [ ] **Step 2: Install dependencies**

```bash
cd src/ui
npm install
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 3: Configure Vitest in `src/ui/vite.config.js`**

Replace the file contents with:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
  },
})
```

- [ ] **Step 4: Create `src/ui/src/test-setup.js`**

```js
import '@testing-library/jest-dom'
```

- [ ] **Step 5: Verify the dev server starts**

```bash
cd src/ui && npm run dev
```

Expected: Vite dev server running at `http://localhost:5173` with the default React scaffold page.

- [ ] **Step 6: Verify tests run**

```bash
npm run test -- --run
```

Expected: No tests yet, exits with 0. If it says "no test files found", that's correct.

- [ ] **Step 7: Add test script to package.json**

In `src/ui/package.json`, ensure the `scripts` block has:
```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "preview": "vite preview",
  "test": "vitest"
}
```

- [ ] **Step 8: Commit**

```bash
git add src/ui/package.json src/ui/vite.config.js src/ui/index.html src/ui/src/main.jsx src/ui/src/test-setup.js src/ui/src/App.jsx src/ui/src/App.css src/ui/src/index.css src/ui/src/assets
git commit -m "feat: scaffold Vite React app for Pythia visualization"
```

---

## Task 2: Design Tokens + Global CSS

**Files:**
- Modify: `src/ui/index.html` — add Google Fonts link
- Overwrite: `src/ui/src/index.css` — tokens + resets

- [ ] **Step 1: Add fonts to `src/ui/index.html`**

In the `<head>` section, add after the existing `<title>`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Syne:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Replace `src/ui/src/index.css` entirely**

```css
:root {
  --bg:            #0D0D0B;
  --surface:       #141410;
  --surface-warm:  #16140E;
  --border:        rgba(255,255,255,0.06);
  --text-primary:  #6A6762;
  --text-muted:    #3D3D38;
  --text-dim:      #1E1E1C;
  --text-ui:       #6E6A66;
  --gold:          #A88C52;
  --gold-dim:      #5E4E28;
  --gold-ui:       #8A7448;

  --font-display: 'Playfair Display', Georgia, serif;
  --font-ui:      'Syne', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'Courier New', monospace;
}

*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
  overflow: hidden;
  background: var(--bg);
  color: var(--text-primary);
  font-family: var(--font-ui);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 3: Delete unused scaffold files**

```bash
cd src/ui
rm -f src/App.css src/assets/react.svg public/vite.svg
```

- [ ] **Step 4: Commit**

```bash
git add src/ui/index.html src/ui/src/index.css
git commit -m "feat: add design tokens and Google Fonts to Pythia UI"
```

---

## Task 3: Scenario Data

**Files:**
- Create: `src/ui/src/simulation/scenarios.js`
- Create: `src/ui/src/simulation/scenarios.test.js`

- [ ] **Step 1: Write the failing test**

Create `src/ui/src/simulation/scenarios.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { SCENARIOS, CROWD_STATES, getScenario } from './scenarios'

describe('scenarios', () => {
  it('CROWD_STATES has 5 entries', () => {
    expect(CROWD_STATES).toHaveLength(5)
  })

  it('each crowd state is a non-empty string', () => {
    CROWD_STATES.forEach(s => expect(typeof s).toBe('string'))
  })

  it('getScenario returns scenario by id', () => {
    const s = getScenario('market-sentiment')
    expect(s).toBeDefined()
    expect(s.name).toContain('Market Sentiment')
  })

  it('each protagonist has required fields', () => {
    const s = getScenario('market-sentiment')
    s.protagonists.forEach(p => {
      expect(p).toHaveProperty('id')
      expect(p).toHaveProperty('name')
      expect(p).toHaveProperty('trait')
      expect(p).toHaveProperty('color')
      expect(p).toHaveProperty('glow')
    })
  })

  it('each scenario has amendments matching protagonist count', () => {
    const s = getScenario('market-sentiment')
    expect(s.amendments).toHaveLength(s.protagonists.length)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd src/ui && npm test -- --run
```

Expected: FAIL — `Cannot find module './scenarios'`

- [ ] **Step 3: Implement `src/ui/src/simulation/scenarios.js`**

```js
export const CROWD_STATES = [
  'Herd Neutrality',
  'Social Contagion',
  'Bandwagon Effect',
  'Groupthink Lock',
  'Deindividuation',
]

export const SCENARIOS = {
  'market-sentiment': {
    name: 'Market Sentiment — Fed Rate Decision',
    protagonists: [
      { id: 'rachel', name: 'Retail Rachel',   trait: 'Loss Aversion',      color: '#B8907A', glow: 'rgba(184,144,122,0.32)' },
      { id: 'ivan',   name: 'Instit. Ivan',    trait: 'Anchoring Bias',      color: '#7A9BA8', glow: 'rgba(122,155,168,0.32)' },
      { id: 'elias',  name: 'Adopter Elias',   trait: 'FOMO Drive',          color: '#A09B7A', glow: 'rgba(160,155,122,0.32)' },
      { id: 'pete',   name: 'Panic Pete',      trait: 'Reactance Theory',    color: '#C08878', glow: 'rgba(192,136,120,0.32)' },
      { id: 'clara',  name: 'Clara C.',        trait: 'Social Reactance',    color: '#8A9B8A', glow: 'rgba(138,155,138,0.32)' },
    ],
    amendments: [
      ['Recalibrating', 'loss threshold...'],
      ['Reweighting',   'anchor signals...'],
      ['Adjusting FOMO', 'sensitivity...'],
      ['Retuning panic', 'trigger curve...'],
      ['Amending social', 'reactance bias...'],
    ],
  },
}

export function getScenario(id) {
  return SCENARIOS[id] ?? null
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd src/ui && npm test -- --run
```

Expected: PASS — 5 tests passing.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/simulation/scenarios.js src/ui/src/simulation/scenarios.test.js
git commit -m "feat: add scenario data with crowd states and protagonist archetypes"
```

---

## Task 4: Simulation Reducer

**Files:**
- Create: `src/ui/src/simulation/reducer.js`
- Create: `src/ui/src/simulation/reducer.test.js`

The reducer holds all sim state as a plain object. It is a pure function (except confidence drift which uses `Math.random` — tests mock this).

- [ ] **Step 1: Write the failing tests**

Create `src/ui/src/simulation/reducer.test.js`:

```js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { simReducer, makeInitialState, TICKS_PER_RUN } from './reducer'

const MOCK_PROTAGONISTS = [
  { id: 'a', name: 'Agent A', trait: 'Trait A', color: '#aaa', glow: 'rgba(0,0,0,0)' },
  { id: 'b', name: 'Agent B', trait: 'Trait B', color: '#bbb', glow: 'rgba(0,0,0,0)' },
]

describe('makeInitialState', () => {
  it('sets tick to 0 and run to 1', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    expect(state.tick).toBe(0)
    expect(state.run).toBe(1)
  })

  it('creates unspawned protoStates for each protagonist', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    expect(state.protoStates).toHaveLength(2)
    state.protoStates.forEach(ps => {
      expect(ps.spawned).toBe(false)
      expect(ps.inTemple).toBe(false)
      expect(ps.returning).toBe(false)
    })
  })

  it('starts with accuracyHistory containing baseline 44', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    expect(state.accuracyHistory).toEqual([44])
  })
})

describe('SPAWN action', () => {
  it('marks protagonist as spawned with given conf', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    const next = simReducer(state, { type: 'SPAWN', idx: 0, conf: 55 })
    expect(next.protoStates[0].spawned).toBe(true)
    expect(next.protoStates[0].conf).toBe(55)
    expect(next.protoStates[1].spawned).toBe(false)
  })
})

describe('TICK action', () => {
  beforeEach(() => { vi.spyOn(Math, 'random').mockReturnValue(0.5) })
  afterEach(() => { vi.restoreAllMocks() })

  it('increments tick by 1', () => {
    const state = { ...makeInitialState(MOCK_PROTAGONISTS), tick: 3 }
    const next = simReducer(state, { type: 'TICK' })
    expect(next.tick).toBe(4)
  })

  it('updates crowdStateIndex based on tick progress', () => {
    // tick 4/20 = 20% through, floor(0.2 * 5) = 1
    const state = { ...makeInitialState(MOCK_PROTAGONISTS), tick: 3 }
    const next = simReducer(state, { type: 'TICK' })
    expect(next.crowdStateIndex).toBe(1)
  })

  it('returns same gen after tick', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    const next = simReducer(state, { type: 'TICK' })
    expect(next.gen).toBe(state.gen)
  })
})

describe('SEND_TO_TEMPLE action', () => {
  it('marks protagonist as inTemple', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    const next = simReducer(state, { type: 'SEND_TO_TEMPLE', idx: 1 })
    expect(next.protoStates[1].inTemple).toBe(true)
    expect(next.templeIdx).toBe(1)
  })
})

describe('RETURN_FROM_TEMPLE action', () => {
  beforeEach(() => { vi.spyOn(Math, 'random').mockReturnValue(0.5) })
  afterEach(() => { vi.restoreAllMocks() })

  it('clears inTemple, sets returning, resets conf high', () => {
    let state = makeInitialState(MOCK_PROTAGONISTS)
    state = simReducer(state, { type: 'SEND_TO_TEMPLE', idx: 0 })
    const next = simReducer(state, { type: 'RETURN_FROM_TEMPLE' })
    expect(next.protoStates[0].inTemple).toBe(false)
    expect(next.protoStates[0].returning).toBe(true)
    expect(next.protoStates[0].conf).toBeGreaterThan(60)
    expect(next.templeIdx).toBeNull()
  })
})

describe('MARK_NOT_RETURNING action', () => {
  it('clears returning flag for given protagonist', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    state.protoStates[0].returning = true
    const next = simReducer(state, { type: 'MARK_NOT_RETURNING', idx: 0 })
    expect(next.protoStates[0].returning).toBe(false)
  })
})

describe('END_RUN action', () => {
  it('resets tick to 0 and increments run', () => {
    const state = { ...makeInitialState(MOCK_PROTAGONISTS), tick: 20, run: 1 }
    const next = simReducer(state, { type: 'END_RUN' })
    expect(next.tick).toBe(0)
    expect(next.run).toBe(2)
  })

  it('pushes a new accuracy value higher than previous', () => {
    const state = makeInitialState(MOCK_PROTAGONISTS)
    const prev = state.accuracyHistory[state.accuracyHistory.length - 1]
    const next = simReducer(state, { type: 'END_RUN' })
    const newAcc = next.accuracyHistory[next.accuracyHistory.length - 1]
    expect(newAcc).toBeGreaterThan(prev)
  })
})

describe('RESET action', () => {
  it('increments gen and resets all state', () => {
    const state = { ...makeInitialState(MOCK_PROTAGONISTS), tick: 15, run: 3, gen: 1 }
    const next = simReducer(state, { type: 'RESET', protagonists: MOCK_PROTAGONISTS })
    expect(next.gen).toBe(2)
    expect(next.tick).toBe(0)
    expect(next.run).toBe(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd src/ui && npm test -- --run
```

Expected: FAIL — `Cannot find module './reducer'`

- [ ] **Step 3: Implement `src/ui/src/simulation/reducer.js`**

```js
import { CROWD_STATES } from './scenarios'

export const TICKS_PER_RUN = 20
const ACCURACY_GAINS = [9, 8, 6, 5, 4, 3, 2]

export function makeInitialState(protagonists) {
  return {
    gen: 0,
    tick: 0,
    run: 1,
    templeIdx: null,
    accuracyHistory: [44],
    accuracy: 44,
    crowdStateIndex: 0,
    protoStates: protagonists.map(() => ({
      spawned: false,
      conf: 0,
      inTemple: false,
      returning: false,
    })),
  }
}

export function simReducer(state, action) {
  switch (action.type) {
    case 'SPAWN': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, spawned: true, conf: action.conf } : ps
      )
      return { ...state, protoStates }
    }

    case 'TICK': {
      const tick = state.tick + 1
      const crowdStateIndex = Math.min(
        Math.floor((tick / TICKS_PER_RUN) * CROWD_STATES.length),
        CROWD_STATES.length - 1
      )
      const protoStates = state.protoStates.map(ps => {
        if (!ps.spawned || ps.inTemple) return ps
        const delta = (Math.random() - 0.46) * 9
        return { ...ps, conf: Math.max(8, Math.min(97, ps.conf + delta)) }
      })
      return { ...state, tick, crowdStateIndex, protoStates }
    }

    case 'SEND_TO_TEMPLE': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, inTemple: true, returning: false } : ps
      )
      return { ...state, protoStates, templeIdx: action.idx }
    }

    case 'RETURN_FROM_TEMPLE': {
      if (state.templeIdx === null) return state
      const idx = state.templeIdx
      const protoStates = state.protoStates.map((ps, i) =>
        i === idx
          ? { ...ps, inTemple: false, returning: true, conf: 68 + Math.random() * 26 }
          : ps
      )
      return { ...state, protoStates, templeIdx: null }
    }

    case 'MARK_NOT_RETURNING': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, returning: false } : ps
      )
      return { ...state, protoStates }
    }

    case 'END_RUN': {
      const gainIdx = Math.min(state.run - 1, ACCURACY_GAINS.length - 1)
      const gain = ACCURACY_GAINS[gainIdx]
      const newAccuracy = Math.min(97, state.accuracy + gain + (Math.random() * 1.5 - 0.75))
      return {
        ...state,
        tick: 0,
        run: state.run + 1,
        templeIdx: null,
        accuracy: newAccuracy,
        accuracyHistory: [...state.accuracyHistory, newAccuracy],
        protoStates: state.protoStates.map(ps =>
          ps.inTemple ? ps : { ...ps, conf: 28 + Math.random() * 32 }
        ),
      }
    }

    case 'RESET': {
      return { ...makeInitialState(action.protagonists), gen: state.gen + 1 }
    }

    default:
      return state
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd src/ui && npm test -- --run
```

Expected: PASS — all reducer tests passing.

- [ ] **Step 5: Commit**

```bash
git add src/ui/src/simulation/reducer.js src/ui/src/simulation/reducer.test.js
git commit -m "feat: add simulation reducer with full tick lifecycle"
```

---

## Task 5: useSimulation Hook

**Files:**
- Create: `src/ui/src/simulation/useSimulation.js`

- [ ] **Step 1: Implement `src/ui/src/simulation/useSimulation.js`**

```js
import { useReducer, useEffect, useCallback, useRef } from 'react'
import { simReducer, makeInitialState, TICKS_PER_RUN } from './reducer'
import { CROWD_STATES } from './scenarios'

const TICK_MS = 2300

export function useSimulation(protagonists, amendments) {
  const [state, dispatch] = useReducer(simReducer, protagonists, makeInitialState)
  const timerRef = useRef(null)

  // Spawn stagger on mount and after reset
  useEffect(() => {
    const gen = state.gen
    const timeouts = protagonists.map((_, i) =>
      setTimeout(() => {
        dispatch({
          type: 'SPAWN',
          idx: i,
          conf: 28 + Math.random() * 28,
        })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, protagonists.length])

  // Tick interval
  useEffect(() => {
    const gen = state.gen
    timerRef.current = setInterval(() => {
      dispatch({ type: 'TICK' })
    }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen])

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

  // Clear returning flag after animation
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
    dispatch({ type: 'RESET', protagonists })
  }, [protagonists])

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / TICKS_PER_RUN) * 100,
    crowdStateIndex: state.crowdStateIndex,
    crowdStateName: CROWD_STATES[state.crowdStateIndex],
    templeIdx: state.templeIdx,
    protoStates: state.protoStates,
    accuracyHistory: state.accuracyHistory,
    amendments,
    restart,
  }
}
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd src/ui && npm run build 2>&1 | head -20
```

Expected: Build succeeds (or fails only on missing components, not on this file).

- [ ] **Step 3: Commit**

```bash
git add src/ui/src/simulation/useSimulation.js
git commit -m "feat: add useSimulation hook with tick engine and temple lifecycle"
```

---

## Task 6: AccuracyCurve Component

**Files:**
- Create: `src/ui/src/components/AccuracyCurve.jsx`

- [ ] **Step 1: Implement `src/ui/src/components/AccuracyCurve.jsx`**

```jsx
export default function AccuracyCurve({ history }) {
  const W = 500, H = 32, PAD = 6
  const MIN_ACC = 30, MAX_ACC = 100

  const coords = history.map((acc, i) => {
    const x = PAD + (i / Math.max(history.length - 1, 1)) * (W - PAD * 2)
    const y = H - PAD - ((acc - MIN_ACC) / (MAX_ACC - MIN_ACC)) * (H - PAD * 2)
    return [x, y]
  })

  const linePoints = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const lastX = coords[coords.length - 1]?.[0] ?? PAD
  const areaD = `M ${PAD},${H} L ${linePoints.replace(',', ' ')} ${lastX.toFixed(1)},${H} Z`
  const current = history[history.length - 1]

  return (
    <footer style={{
      height: 64,
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 28px',
      gap: 18,
      flexShrink: 0,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
        color: 'var(--text-ui)',
        whiteSpace: 'nowrap',
        lineHeight: 1.6,
      }}>
        Prediction<br />Accuracy
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
        style={{ flex: 1, height: 32, overflow: 'visible' }}>
        <defs>
          <linearGradient id="acc-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#C4A96A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#C4A96A" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#acc-grad)" stroke="none" />
        <polyline points={linePoints} fill="none" stroke="#A88C52"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 20,
        fontWeight: 300,
        color: 'var(--text-primary)',
        letterSpacing: '-0.03em',
        whiteSpace: 'nowrap',
      }}>
        {current != null ? Math.round(current) : '—'}
        <span style={{ fontSize: 9, color: 'var(--text-muted)', verticalAlign: 'super', marginLeft: 1 }}>%</span>
      </div>
    </footer>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/src/components/AccuracyCurve.jsx
git commit -m "feat: add AccuracyCurve SVG component"
```

---

## Task 7: Header Component

**Files:**
- Create: `src/ui/src/components/Header.jsx`

- [ ] **Step 1: Implement `src/ui/src/components/Header.jsx`**

```jsx
export default function Header({ scenarioName, tick, run, progressPercent, onRestart }) {
  const tickStr = String(tick).padStart(2, '0')
  const runStr  = String(run).padStart(2, '0')

  return (
    <>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '18px 28px 14px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--text-primary)',
        }}>
          Pythia
          <span style={{
            fontStyle: 'normal',
            fontFamily: 'var(--font-ui)',
            fontWeight: 300,
            fontSize: 14,
            color: 'var(--gold)',
            letterSpacing: '0.04em',
          }}>◈ ORACLE</span>
        </div>

        {/* Scenario */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 300,
            fontSize: 9,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--text-ui)',
          }}>Active Scenario</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 500,
            fontSize: 13,
            color: 'var(--text-primary)',
            marginTop: 3,
          }}>{scenarioName}</div>
        </div>

        {/* Tick + Restart */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <button
            onClick={onRestart}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--gold-ui)',
              background: 'none',
              border: '1px solid var(--gold-ui)',
              padding: '5px 12px',
              cursor: 'pointer',
            }}
          >↺ Restart</button>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-muted)',
              letterSpacing: '0.12em',
            }}>TICK</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 22,
              fontWeight: 300,
              color: 'var(--text-primary)',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              marginTop: 2,
            }}>{tickStr} / 20</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--gold-dim)',
              letterSpacing: '0.1em',
              marginTop: 2,
            }}>RUN · {runStr}</div>
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div style={{ height: 1, background: 'var(--text-dim)', flexShrink: 0 }}>
        <div style={{
          height: '100%',
          background: 'var(--gold)',
          width: `${progressPercent}%`,
          transition: 'width 1s cubic-bezier(0.4,0,0.2,1)',
          boxShadow: '0 0 6px var(--gold)',
        }} />
      </div>
    </>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/src/components/Header.jsx
git commit -m "feat: add Header component with tick display and restart button"
```

---

## Task 8: Stage Component (Protagonists)

**Files:**
- Create: `src/ui/src/components/Stage.jsx`

- [ ] **Step 1: Implement `src/ui/src/components/Stage.jsx`**

```jsx
import { useEffect, useRef } from 'react'

const CIRC = 2 * Math.PI * 18   // r=18, circumference ≈ 113.1

function ProtagNode({ protagonist, state, delay }) {
  const dotRef = useRef(null)

  // Flash animation on return from temple
  useEffect(() => {
    if (!state.returning || !dotRef.current) return
    dotRef.current.animate([
      { boxShadow: '0 0 0 0 rgba(196,169,106,0)' },
      { boxShadow: '0 0 28px 10px rgba(196,169,106,0.55)' },
      { boxShadow: '0 0 8px 3px rgba(196,169,106,0.18)' },
    ], { duration: 1400, fill: 'forwards' })
  }, [state.returning])

  const visible  = state.spawned
  const inTemple = state.inTemple
  const conf     = state.conf
  const dashOffset = CIRC * (1 - conf / 100)

  const opacity   = inTemple ? 0.25 : 1
  const translateX = inTemple ? 16 : 0

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '10px 0',
      borderBottom: '1px solid rgba(255,255,255,0.028)',
      opacity: visible ? opacity : 0,
      transform: `translateX(${visible ? translateX : -12}px)`,
      transition: `opacity 0.7s ease ${delay}s, transform 0.7s ease ${delay}s`,
    }}>
      {/* Ring + Dot */}
      <div style={{ position: 'relative', width: 42, height: 42, flexShrink: 0 }}>
        <svg style={{ position: 'absolute', inset: 0, width: 42, height: 42 }}
          viewBox="0 0 42 42">
          <circle cx="21" cy="21" r="18" fill="none"
            stroke="var(--text-dim)" strokeWidth="1.5" />
          <circle cx="21" cy="21" r="18" fill="none"
            stroke={inTemple ? '#5A4A28' : protagonist.color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={dashOffset}
            style={{
              transformOrigin: '21px 21px',
              transform: 'rotate(-90deg)',
              transition: 'stroke-dashoffset 1.1s cubic-bezier(0.4,0,0.2,1), stroke 0.9s ease',
            }}
          />
        </svg>
        <div
          ref={dotRef}
          style={{
            position: 'absolute',
            inset: 0,
            margin: 'auto',
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: protagonist.color,
            opacity: visible ? 1 : 0,
            transition: 'opacity 0.9s ease',
            animation: visible && !inTemple ? `dot-pulse 2.8s ease-in-out ${delay}s infinite` : 'none',
            '--glow': protagonist.glow,
          }}
        />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 600,
          fontSize: 11.5,
          color: 'var(--text-primary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>{protagonist.name}</div>
        <div style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 300,
          fontSize: 9.5,
          color: 'var(--gold)',
          marginTop: 2,
          opacity: visible ? 1 : 0,
          transition: 'opacity 1.2s ease 0.5s',
        }}>{protagonist.trait}</div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          marginTop: 3,
        }}>{visible ? `${Math.round(conf)}%` : '—'}</div>
      </div>
    </div>
  )
}

export default function Stage({ protagonists, protoStates }) {
  return (
    <div style={{
      width: 210,
      flexShrink: 0,
      borderRight: '1px solid var(--border)',
      padding: '20px 18px',
      overflowY: 'auto',
    }}>
      <style>{`
        @keyframes dot-pulse {
          0%, 100% { box-shadow: 0 0 6px 2px var(--glow); }
          50%       { box-shadow: 0 0 18px 7px var(--glow); }
        }
      `}</style>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: 'var(--text-ui)',
        marginBottom: 18,
      }}>// The Stage</div>

      {protagonists.map((p, i) => (
        <ProtagNode
          key={p.id}
          protagonist={p}
          state={protoStates[i]}
          delay={i * 0.1}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/src/components/Stage.jsx
git commit -m "feat: add Stage component with ProtagNode lifecycle animations"
```

---

## Task 9: Arena Component (Crowd Particles)

**Files:**
- Create: `src/ui/src/components/Arena.jsx`

- [ ] **Step 1: Implement `src/ui/src/components/Arena.jsx`**

```jsx
import { useRef, useEffect } from 'react'
import { CROWD_STATES } from '../simulation/scenarios'

const C_REST   = [58,  58,  56]
const C_ACTIVE = [200, 194, 185]
const C_PANIC  = [160, 72,  60]

function lerpRGB(a, b, t) {
  return a.map((v, i) => Math.round(v + (b[i] - v) * t))
}

function crowdConfig(stateIdx, W, H) {
  const cx = W / 2, cy = H / 2
  return [
    { attr: 0,       cx, cy,          spd: 0.28, ct: 0,    chaos: 0,   panic: false },
    { attr: 0.004,   cx, cy,          spd: 0.55, ct: 0.42, chaos: 0,   panic: false },
    { attr: 0.009,   cx, cy: cy*0.85, spd: 0.75, ct: 0.72, chaos: 0.12,panic: false },
    { attr: 0.022,   cx, cy: cy*0.65, spd: 0.35, ct: 0.92, chaos: 0,   panic: false },
    { attr: -0.006,  cx, cy,          spd: 2.6,  ct: 0.55, chaos: 1.8, panic: true  },
  ][stateIdx] ?? { attr: 0, cx, cy, spd: 0.3, ct: 0, chaos: 0, panic: false }
}

function initParticles(W, H, count = 290) {
  return Array.from({ length: count }, () => ({
    x:  Math.random() * W,
    y:  Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    sz: 2.2 + Math.random() * 1.4,
    ct: 0,
  }))
}

export default function Arena({ crowdStateIndex, crowdStateName }) {
  const canvasRef  = useRef(null)
  const stateRef   = useRef({ particles: [], crowdStateIndex: 0 })
  const rafRef     = useRef(null)

  useEffect(() => {
    stateRef.current.crowdStateIndex = crowdStateIndex
  }, [crowdStateIndex])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    function resize() {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      if (!W || !H) return
      const dpr = window.devicePixelRatio || 1
      canvas.width  = W * dpr
      canvas.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      stateRef.current.particles = initParticles(W, H)
    }

    function frame() {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      if (!W || !H) { rafRef.current = requestAnimationFrame(frame); return }

      const cfg = crowdConfig(stateRef.current.crowdStateIndex, W, H)
      ctx.clearRect(0, 0, W, H)

      stateRef.current.particles.forEach(p => {
        if (cfg.attr !== 0) {
          p.vx += (cfg.cx - p.x) * cfg.attr
          p.vy += (cfg.cy - p.y) * cfg.attr
        }
        if (cfg.chaos > 0) {
          p.vx += (Math.random() - 0.5) * cfg.chaos
          p.vy += (Math.random() - 0.5) * cfg.chaos
        }
        const spd = Math.hypot(p.vx, p.vy)
        if (spd > cfg.spd) { p.vx = p.vx / spd * cfg.spd; p.vy = p.vy / spd * cfg.spd }
        p.vx *= 0.98; p.vy *= 0.98
        p.x += p.vx;  p.y += p.vy
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0
        if (p.y < 0) p.y = H; if (p.y > H) p.y = 0
        p.ct += (cfg.ct - p.ct) * 0.018

        const rgb = cfg.panic
          ? lerpRGB(C_REST, C_PANIC, p.ct)
          : lerpRGB(C_REST, C_ACTIVE, p.ct)
        const alpha = 0.38 + p.ct * 0.48
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.sz, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`
        ctx.fill()
      })

      rafRef.current = requestAnimationFrame(frame)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    resize()
    rafRef.current = requestAnimationFrame(frame)

    return () => {
      ro.disconnect()
      cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      <div style={{
        position: 'absolute',
        bottom: 14,
        left: 0, right: 0,
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
        fontSize: 8.5,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        color: 'var(--text-ui)',
        pointerEvents: 'none',
      }}>{crowdStateName}</div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/src/components/Arena.jsx
git commit -m "feat: add Arena canvas component with crowd particle system"
```

---

## Task 10: Temple Component

**Files:**
- Create: `src/ui/src/components/Temple.jsx`

- [ ] **Step 1: Implement `src/ui/src/components/Temple.jsx`**

```jsx
import { useEffect, useRef, useState } from 'react'

function TypewriterText({ lines }) {
  const [displayed, setDisplayed] = useState('')
  const fullText = lines.join(' ')

  useEffect(() => {
    setDisplayed('')
    let i = 0
    const id = setInterval(() => {
      if (i >= fullText.length) { clearInterval(id); return }
      setDisplayed(fullText.slice(0, i + 1))
      i++
    }, 44)
    return () => clearInterval(id)
  }, [fullText])

  return (
    <div style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 8.5,
      color: 'var(--text-muted)',
      textAlign: 'center',
      lineHeight: 1.9,
      letterSpacing: '0.02em',
      minHeight: 36,
    }}>{displayed}</div>
  )
}

export default function Temple({ protagonist, amendment }) {
  const active = protagonist !== null

  return (
    <div style={{
      width: 190,
      flexShrink: 0,
      borderLeft: '1px solid var(--border)',
      background: 'var(--surface-warm)',
      padding: '20px 16px',
      position: 'relative',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Ambient glow */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(ellipse 80% 50% at 50% 100%, rgba(196,169,106,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <style>{`
        @keyframes temple-spin { to { transform: rotate(360deg); } }
      `}</style>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: 'var(--gold-ui)',
        marginBottom: 18,
        flexShrink: 0,
      }}>// Temple of Learning</div>

      {/* Idle */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        opacity: active ? 0 : 1,
        transition: 'opacity 0.5s ease',
        position: active ? 'absolute' : 'relative',
        pointerEvents: 'none',
      }}>
        <div style={{ width: 24, height: 1, background: 'var(--text-muted)' }} />
        <div style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 11,
          color: 'var(--text-ui)',
          textAlign: 'center',
          lineHeight: 1.8,
        }}>The oracle<br />awaits the<br />fallen</div>
        <div style={{ width: 24, height: 1, background: 'var(--text-muted)' }} />
      </div>

      {/* Active */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        opacity: active ? 1 : 0,
        transform: active ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.7s ease, transform 0.7s ease',
      }}>
        {protagonist && (
          <>
            <div style={{ width: 44, height: 44, position: 'relative' }}>
              <svg viewBox="0 0 44 44" style={{ width: 44, height: 44, animation: 'temple-spin 3.5s linear infinite' }}>
                <circle cx="22" cy="22" r="17" fill="none"
                  stroke="var(--gold)" strokeWidth="1"
                  strokeLinecap="round"
                  strokeDasharray="90 20" opacity="0.8" />
              </svg>
              <div style={{
                position: 'absolute',
                inset: 0,
                margin: 'auto',
                width: 20,
                height: 20,
                borderRadius: '50%',
                background: protagonist.color,
              }} />
            </div>

            <div style={{
              fontFamily: 'var(--font-ui)',
              fontWeight: 500,
              fontSize: 11,
              color: 'var(--gold)',
              letterSpacing: '0.02em',
            }}>{protagonist.name}</div>

            <TypewriterText key={protagonist.id} lines={amendment} />
          </>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/src/components/Temple.jsx
git commit -m "feat: add Temple component with idle/active states and typewriter"
```

---

## Task 11: Wire Up App.jsx

**Files:**
- Overwrite: `src/ui/src/App.jsx`

- [ ] **Step 1: Implement `src/ui/src/App.jsx`**

```jsx
import { useSimulation } from './simulation/useSimulation'
import { getScenario } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'

const SCENARIO_ID = 'market-sentiment'

export default function App() {
  const scenario = getScenario(SCENARIO_ID)

  const sim = useSimulation(scenario.protagonists, scenario.amendments)

  const templeProtagonist = sim.templeIdx !== null
    ? scenario.protagonists[sim.templeIdx]
    : null

  const templeAmendment = sim.templeIdx !== null
    ? scenario.amendments[sim.templeIdx]
    : ['', '']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
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
    </div>
  )
}
```

- [ ] **Step 2: Run the dev server and verify visually**

```bash
cd src/ui && npm run dev
```

Open `http://localhost:5173`. Expected:
- Dark canvas layout with three zones visible
- Protagonists spawn one-by-one over ~2 seconds on the left
- Particles animate in the center
- Tick counter advances every 2.3 seconds
- At tick 9, a protagonist enters the Temple with spinner + typewriter
- At tick 16, they return with gold flash
- Accuracy curve updates after each run
- Restart button resets everything

- [ ] **Step 3: Run full test suite**

```bash
cd src/ui && npm test -- --run
```

Expected: All tests pass (reducer + scenarios).

- [ ] **Step 4: Final commit**

```bash
git add src/ui/src/App.jsx src/ui/src/components/
git commit -m "feat: wire up App.jsx — full Pythia visualization running"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Three-zone layout (Stage 210px / Arena flex / Temple 190px)
- ✅ Protagonist lifecycle: spawn stagger, taking character, active pulse, Temple entry/exit, gold flash
- ✅ Confidence ring via SVG `stroke-dashoffset`
- ✅ Crowd states (5 states, fluid lerp, label)
- ✅ Temple idle + active + typewriter + spinner
- ✅ Header: logo, scenario, tick, run, restart, progress bar
- ✅ Footer: SVG accuracy curve with gradient area
- ✅ Design tokens: all CSS variables match spec
- ✅ Font stack: Playfair Display, Syne, JetBrains Mono
- ✅ Scenario data driving protagonist roster

**Placeholder scan:** None found — all code steps contain complete implementations.

**Type consistency:**
- `useSimulation` returns `protoStates[i].{ spawned, conf, inTemple, returning }` — consumed identically in `Stage.jsx`
- `templeIdx` is `number | null` — checked correctly in `App.jsx`
- `accuracyHistory` is `number[]` — consumed correctly in `AccuracyCurve`
- `amendments[idx]` is `string[]` — passed as `lines` to `TypewriterText`
