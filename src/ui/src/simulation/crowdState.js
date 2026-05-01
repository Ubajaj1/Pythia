/**
 * Crowd state classifier — reads real tick data and picks one of five
 * observable patterns based on the distribution of agent stances, the
 * movement of the aggregate, and the presence of herd-pressure influence edges.
 *
 * Replaces the earlier time-based progression, which was cosmetic and
 * misleading — it advanced through the same five labels regardless of what
 * the simulation actually did.
 *
 * States (ordered by severity, higher = tighter/stronger crowd effect):
 *   0 Scattered   — spread out, no strong lean
 *   1 Drifting    — aggregate moving, agents adjusting
 *   2 Converging  — narrowing + active herd pressure
 *   3 Locked      — tight consensus, very little movement
 *   4 Polarized   — split camps, wide spread that doesn't close
 *
 * The index is used as a visual intensity knob by the Arena particle
 * animation (crowdConfig). The NAME is what users read, so the names
 * must describe what's really happening.
 */

export const CROWD_STATES = [
  'Scattered',
  'Drifting',
  'Converging',
  'Locked',
  'Polarized',
]

// ── Thresholds ───────────────────────────────────────────────────────────
// Tunable. Picked by inspection of real runs; adjust as we learn.

// Standard deviation of agent stances — tight vs. spread-out panel.
const SIGMA_TIGHT  = 0.08   // below this = locked / near-consensus
const SIGMA_WIDE   = 0.18   // above this = scattered or polarized

// Spread = max − min agent stance. A panel can be high-σ because it's
// evenly spread (scattered) OR because two camps diverge (polarized).
// Spread helps distinguish those: if σ is high AND spread is very wide,
// call it polarized rather than scattered.
const SPREAD_POLARIZED = 0.50

// Aggregate drift — how much the mean moved over the last few ticks.
const AGG_MOVING     = 0.04  // per tick, sustained = drifting
const AGG_STILL      = 0.02  // tiny movement = locked / quiescent

// How far from neutral (0.5) the aggregate must be to count as "leaning."
const LEAN_THRESHOLD = 0.15

// ── Helpers ──────────────────────────────────────────────────────────────

function mean(xs) {
  if (!xs.length) return 0
  let s = 0
  for (const x of xs) s += x
  return s / xs.length
}

function stdev(xs) {
  if (xs.length < 2) return 0
  const m = mean(xs)
  let s = 0
  for (const x of xs) s += (x - m) * (x - m)
  return Math.sqrt(s / xs.length)
}

function spread(xs) {
  if (!xs.length) return 0
  let lo = xs[0], hi = xs[0]
  for (const x of xs) {
    if (x < lo) lo = x
    if (x > hi) hi = x
  }
  return hi - lo
}

/**
 * Build a map of agent_id → latest stance from the events recorded
 * on the given tick. Used to sample the panel's distribution at a point in time.
 */
function stancesAtTick(tickData) {
  const out = []
  if (!tickData?.events) return out
  for (const ev of tickData.events) {
    if (typeof ev.stance === 'number') out.push(ev.stance)
  }
  return out
}

/**
 * Count herd-pressure edges that arrived on the given tick.
 * Herd edges are ones created by the engine when an agent moved in
 * the same direction as the aggregate without an explicit message.
 */
function herdEdgesOnTick(influenceEdges, tick) {
  if (!Array.isArray(influenceEdges)) return 0
  let n = 0
  for (const e of influenceEdges) {
    if (e?.tick === tick && e?.edge_type === 'herd_pressure') n++
  }
  return n
}

// ── Classifier ───────────────────────────────────────────────────────────

/**
 * Classify the crowd state at `currentTick` given the full tick history.
 *
 * @param {Array} ticks — array of { tick, events:[{stance}], aggregate_stance }
 * @param {number} currentTick — 1-based tick index being displayed
 * @param {Array} influenceEdges — optional list from influence_graph.edges
 * @returns {{ index: number, name: string }}
 */
export function classifyCrowdState(ticks, currentTick, influenceEdges = []) {
  // No data yet — can't honestly say anything. Default to Scattered (index 0),
  // which animates as a low-energy, neutral particle field.
  if (!ticks?.length || currentTick < 1) {
    return { index: 0, name: CROWD_STATES[0] }
  }

  const clampedTick = Math.min(currentTick, ticks.length)
  const visible = ticks.slice(0, clampedTick)
  const latest = visible[visible.length - 1]
  if (!latest) return { index: 0, name: CROWD_STATES[0] }

  const stances = stancesAtTick(latest)
  if (stances.length < 2) {
    return { index: 0, name: CROWD_STATES[0] }
  }

  const sigma = stdev(stances)
  const sprd  = spread(stances)
  const agg   = typeof latest.aggregate_stance === 'number'
    ? latest.aggregate_stance
    : mean(stances)

  // Aggregate movement over the last 2 ticks (so we have some smoothing)
  let aggDelta = 0
  if (visible.length >= 2) {
    const prev = visible[visible.length - 2]
    if (typeof prev?.aggregate_stance === 'number') {
      aggDelta = Math.abs(agg - prev.aggregate_stance)
    }
  }
  // Also look back 3 ticks for the "locked" check (needs sustained quiet)
  let aggDelta3 = aggDelta
  if (visible.length >= 4) {
    const prev3 = visible[visible.length - 4]
    if (typeof prev3?.aggregate_stance === 'number') {
      aggDelta3 = Math.abs(agg - prev3.aggregate_stance)
    }
  }

  const herdCount = herdEdgesOnTick(influenceEdges, latest.tick)

  // ── Decision tree ─────────────────────────────────────────────────────
  // Order matters — more specific patterns first.

  // Polarized: wide spread AND wide σ → two camps that aren't closing.
  if (sprd > SPREAD_POLARIZED && sigma > SIGMA_WIDE) {
    return { index: 4, name: CROWD_STATES[4] }
  }

  // Locked: tight σ AND aggregate hasn't moved over ~3 ticks → consensus.
  // We also require the aggregate to have actually *picked* a side (not neutral),
  // and demand at least 3 ticks of history — "sustained quiet" needs evidence.
  if (
    visible.length >= 3 &&
    sigma < SIGMA_TIGHT &&
    aggDelta3 < AGG_STILL * 3 &&
    Math.abs(agg - 0.5) > LEAN_THRESHOLD
  ) {
    return { index: 3, name: CROWD_STATES[3] }
  }

  // Converging: σ narrowing AND herd pressure active this tick.
  // We detect narrowing by comparing current σ to σ two ticks back.
  if (visible.length >= 3) {
    const sigmaPrev = stdev(stancesAtTick(visible[visible.length - 3]))
    const narrowing = sigmaPrev > 0 && sigma < sigmaPrev - 0.01
    if (narrowing && herdCount >= 1) {
      return { index: 2, name: CROWD_STATES[2] }
    }
  }

  // Drifting: the aggregate is moving meaningfully this tick.
  if (aggDelta > AGG_MOVING) {
    return { index: 1, name: CROWD_STATES[1] }
  }

  // Otherwise: scattered (spread out, no strong lean, no active herding).
  return { index: 0, name: CROWD_STATES[0] }
}
