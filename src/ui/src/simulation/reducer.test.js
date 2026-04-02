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
