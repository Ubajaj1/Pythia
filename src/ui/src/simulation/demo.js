/**
 * Demo mode — plays a pre-seeded mock simulation through the same SSE event
 * pipeline as real API calls, so every component renders identically.
 */

export const DEMO_AGENTS = [
  { id: 'rachel', name: 'Retail Rachel',  role: 'Retail Investor',       bias: 'Loss Aversion',    initial_stance: 0.35 },
  { id: 'ivan',   name: 'Instit. Ivan',   role: 'Institutional Trader',  bias: 'Anchoring Bias',   initial_stance: 0.65 },
  { id: 'elias',  name: 'Adopter Elias',  role: 'Early Adopter',         bias: 'FOMO Drive',       initial_stance: 0.55 },
  { id: 'pete',   name: 'Panic Pete',     role: 'Momentum Trader',       bias: 'Reactance Theory', initial_stance: 0.25 },
  { id: 'clara',  name: 'Clara C.',       role: 'Social Trader',         bias: 'Social Reactance', initial_stance: 0.45 },
]

const DEMO_SCENARIO_META = {
  title: 'Market Sentiment — Fed Rate Decision',
  scenario_type: 'market_analysis',
  stance_spectrum: ['Strong Sell', 'Reduce', 'Hold', 'Accumulate', 'Strong Buy'],
  tick_count: 20,
}

const ACTIONS = [
  'holds position', 'revises forecast', 'signals caution',
  'adjusts exposure', 'recalibrates', 'monitors developments',
  'updates model', 'reassesses risk', 'consolidates view', 'shifts allocation',
]

const EMOTIONS = ['cautious', 'uncertain', 'confident', 'anxious', 'resolute', 'measured', 'concerned']

const REASONINGS = {
  'Loss Aversion':    [
    'Risk of loss outweighs potential gain at current levels.',
    'Preserving capital is the priority given the uncertainty.',
    'The downside scenario looks more probable than upside.',
  ],
  'Anchoring Bias':   [
    'Fundamentals anchor me near fair value despite short-term noise.',
    'My valuation model still points to the same level.',
    'Group sentiment is overreacting — my anchor holds.',
  ],
  'FOMO Drive':       [
    'Momentum is shifting — I need to follow the consensus.',
    'Missing this move would be costly; adjusting accordingly.',
    'The trend is clear; staying ahead of the crowd.',
  ],
  'Reactance Theory': [
    'Everyone is moving one way, so I see opportunity the other.',
    'Contrarian signal: group consensus is too strong.',
    'The herd is wrong here — my instinct says opposite.',
  ],
  'Social Reactance': [
    'The group consensus is informative; updating my view.',
    'Peer signals suggest repositioning is warranted.',
    'Aligning with collective intelligence on this one.',
  ],
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

function generateDemoTicks(agents, tickCount = 20) {
  // Seed a fixed random sequence so demo looks the same every time
  let seed = 42
  function seededRandom() {
    seed = (seed * 1664525 + 1013904223) & 0xffffffff
    return (seed >>> 0) / 0xffffffff
  }

  const stances = Object.fromEntries(agents.map(a => [a.id, a.initial_stance]))
  const ticks = []

  for (let tick = 1; tick <= tickCount; tick++) {
    const aggregate = Object.values(stances).reduce((s, v) => s + v, 0) / agents.length
    const events = []

    agents.forEach((agent, agentIdx) => {
      const prev = stances[agent.id]
      const noise = (seededRandom() - 0.5) * 0.05
      let delta = 0

      if (agent.bias === 'Loss Aversion') {
        delta = (aggregate - prev) * 0.10 - 0.012 + noise
      } else if (agent.bias === 'Anchoring Bias') {
        delta = (agent.initial_stance - prev) * 0.15 + (aggregate - prev) * 0.06 + noise * 0.6
      } else if (agent.bias === 'FOMO Drive') {
        delta = (aggregate - prev) * 0.32 + noise
      } else if (agent.bias === 'Reactance Theory') {
        delta = (prev - aggregate) * 0.20 + noise * 1.4
      } else {
        delta = (aggregate - prev) * 0.22 + noise
      }

      const newStance = Math.round(clamp(prev + delta, 0.05, 0.95) * 1000) / 1000
      stances[agent.id] = newStance

      const reasonings = REASONINGS[agent.bias]
      events.push({
        agent_id: agent.id,
        stance: newStance,
        previous_stance: Math.round(prev * 1000) / 1000,
        action: ACTIONS[(tick + agentIdx) % ACTIONS.length],
        emotion: EMOTIONS[Math.floor(seededRandom() * EMOTIONS.length)],
        reasoning: reasonings[tick % reasonings.length],
        message: `Aggregate at ${aggregate.toFixed(2)} — ${newStance > prev ? 'adjusting up' : 'pulling back'}.`,
        influence_target: null,
      })
    })

    const newAggregate = Object.values(stances).reduce((s, v) => s + v, 0) / agents.length
    ticks.push({ tick, events, aggregate_stance: Math.round(newAggregate * 10000) / 10000 })
  }

  return ticks
}

/**
 * Replay a mock simulation by emitting SSE-equivalent events via onEvent.
 * Returns a cancel function — call it to abort mid-demo.
 */
export function startDemoStream(onEvent) {
  const ticks = generateDemoTicks(DEMO_AGENTS, DEMO_SCENARIO_META.tick_count)
  let cancelled = false
  const ids = []

  function after(ms, fn) {
    const id = setTimeout(() => { if (!cancelled) fn() }, ms)
    ids.push(id)
  }

  // thinking → layout appears immediately
  onEvent({ type: 'thinking' })

  // blueprint → title appears while "agents are being generated"
  after(700, () => onEvent({
    type: 'blueprint',
    data: {
      title: DEMO_SCENARIO_META.title,
      tick_count: DEMO_SCENARIO_META.tick_count,
      stance_spectrum: DEMO_SCENARIO_META.stance_spectrum,
    },
  }))

  // scenario → real agents replace the skeleton
  after(2000, () => onEvent({
    type: 'scenario',
    data: { ...DEMO_SCENARIO_META, agents: DEMO_AGENTS },
  }))

  // push all tick data quickly into the buffer right after scenario;
  // visual pacing is controlled by the 2300ms TICK_MS timer in useStreamingSimulation
  ticks.forEach((tick, i) => {
    after(2100 + i * 80, () => onEvent({ type: 'tick', data: tick }))
  })

  after(2100 + ticks.length * 80 + 200, () => onEvent({ type: 'done' }))

  return () => {
    cancelled = true
    ids.forEach(clearTimeout)
  }
}
