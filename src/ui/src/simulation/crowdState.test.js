import { describe, it, expect } from 'vitest'
import { classifyCrowdState, CROWD_STATES } from './crowdState'

// ── Helpers ──────────────────────────────────────────────────────────────

/** Build a tick with a fixed list of stances; aggregate = mean. */
function makeTick(tick, stances) {
  const agg = stances.reduce((s, v) => s + v, 0) / stances.length
  return {
    tick,
    events: stances.map((s, i) => ({ agent_id: `a${i}`, stance: s })),
    aggregate_stance: Math.round(agg * 10000) / 10000,
  }
}

/** Build a herd-pressure edge at a given tick. */
function herdEdge(tick, agentId = 'a0') {
  return {
    tick,
    edge_type: 'herd_pressure',
    source_id: '__aggregate__',
    target_id: agentId,
  }
}

// ── Tests ────────────────────────────────────────────────────────────────

describe('classifyCrowdState', () => {
  it('returns Scattered with no ticks', () => {
    const { index, name } = classifyCrowdState([], 0)
    expect(index).toBe(0)
    expect(name).toBe(CROWD_STATES[0])
  })

  it('returns Scattered when currentTick is below 1', () => {
    const ticks = [makeTick(1, [0.4, 0.5, 0.6])]
    const { index } = classifyCrowdState(ticks, 0)
    expect(index).toBe(0)
  })

  it('classifies a wide, still panel near neutral as Scattered', () => {
    // σ ≈ 0.16, spread 0.4, agg ≈ 0.5 → not polarized, not drifting, not locked
    const ticks = [
      makeTick(1, [0.3, 0.5, 0.7, 0.5, 0.4, 0.6]),
      makeTick(2, [0.3, 0.5, 0.7, 0.5, 0.4, 0.6]),
    ]
    const { name } = classifyCrowdState(ticks, 2)
    expect(name).toBe('Scattered')
  })

  it('classifies a moving aggregate as Drifting', () => {
    // Aggregate jumps 0.50 → 0.58 between ticks (delta > 0.04 threshold)
    const ticks = [
      makeTick(1, [0.45, 0.50, 0.55]),  // agg 0.50
      makeTick(2, [0.55, 0.58, 0.62]),  // agg 0.583
    ]
    const { name } = classifyCrowdState(ticks, 2)
    expect(name).toBe('Drifting')
  })

  it('classifies narrowing stances with herd edges as Converging', () => {
    // σ shrinks 0.20 → 0.05 AND a herd edge fires on the latest tick.
    const ticks = [
      makeTick(1, [0.3, 0.5, 0.7]),     // σ ≈ 0.163
      makeTick(2, [0.4, 0.5, 0.6]),     // σ ≈ 0.082
      makeTick(3, [0.48, 0.5, 0.52]),   // σ ≈ 0.016
    ]
    const edges = [herdEdge(3)]
    const { name } = classifyCrowdState(ticks, 3, edges)
    expect(name).toBe('Converging')
  })

  it('classifies a tight, still, leaning panel as Locked', () => {
    // σ < 0.08, aggregate parked at 0.80 (|agg - 0.5| > 0.15), and flat for 3+ ticks.
    const stances = [0.78, 0.80, 0.82]
    const ticks = [
      makeTick(1, stances),
      makeTick(2, stances),
      makeTick(3, stances),
      makeTick(4, stances),
    ]
    const { name } = classifyCrowdState(ticks, 4)
    expect(name).toBe('Locked')
  })

  it('classifies two-camp split (wide spread + wide σ) as Polarized', () => {
    // Matches the actual RTO run: σ = 0.19, spread = 0.57.
    // Employees near the bottom, managers/HR/CEO near the top.
    const stances = [0.39, 0.96, 0.80, 0.77, 0.95, 0.85]
    const ticks = [
      makeTick(1, stances),
      makeTick(2, stances),
    ]
    const { name } = classifyCrowdState(ticks, 2)
    expect(name).toBe('Polarized')
  })

  it('falls back to Scattered when fewer than 2 agents reported', () => {
    const ticks = [makeTick(1, [0.7])]
    const { name } = classifyCrowdState(ticks, 1)
    expect(name).toBe('Scattered')
  })

  it('clamps currentTick beyond the tick array', () => {
    const ticks = [makeTick(1, [0.78, 0.80, 0.82])]
    const { name } = classifyCrowdState(ticks, 999)
    // Only one tick available; no prior comparison possible. Not drifting/
    // converging/locked. Agg = 0.80 and σ ≈ 0.016, spread 0.04 → Scattered.
    expect(name).toBe('Scattered')
  })
})
