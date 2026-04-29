/**
 * Demo mode — plays a pre-seeded mock simulation through the same SSE event
 * pipeline as real API calls, so every component renders identically.
 *
 * The demo is a scripted Fed-rate-decision scenario with 5 agents. It emits:
 *   thinking → blueprint → scenario → [20 tick events] → done
 *
 * The `done` event carries a hand-crafted decision_summary (full Oracle
 * verdict with arguments/risks/takeaways), an influence_graph with a few
 * edges including one herd_pressure edge, and a methodology block — all
 * shaped exactly like the real backend emits so DecisionPanel, AgentDetail,
 * OracleMethod, and the Temple of Learning all render without needing any
 * special-casing for demo data.
 */

// Biases use canonical catalog names (matching src/pythia/biases.py) so the
// Oracle's Method panel shows the exact same labels as real runs. The
// `bias_mechanics` field is a UI-only hint for reasoning templates — it maps
// 1:1 to a canonical bias but keeps the demo's deterministic tick math stable.
export const DEMO_AGENTS = [
  {
    id: 'rachel',
    name: 'Retail Rachel',
    role: 'Retail Investor',
    persona: 'Long-term dollar-cost-average saver with a 401k heavy in index funds. Gets most market news from Twitter and weekend newsletters. Has lived through one serious drawdown and never forgot it.',
    bias: 'Loss Aversion',
    bias_mechanics: 'loss_aversion',
    initial_stance: 0.35,
  },
  {
    id: 'ivan',
    name: 'Instit. Ivan',
    role: 'Institutional Trader',
    persona: 'Mid-career quant on a rates desk at a macro fund. Runs a mean-reversion book with a disciplined valuation anchor. Trusts models over narratives.',
    bias: 'Anchoring Bias',
    bias_mechanics: 'anchoring',
    initial_stance: 0.65,
  },
  {
    id: 'elias',
    name: 'Adopter Elias',
    role: 'Early Adopter',
    persona: 'Growth-stage founder who moonlights as an angel investor. Leans into momentum plays and believes "being early" is its own edge.',
    bias: 'Optimism Bias',
    bias_mechanics: 'optimism',
    initial_stance: 0.55,
  },
  {
    id: 'pete',
    name: 'Panic Pete',
    role: 'Momentum Trader',
    persona: 'Day-trader who built his book on sentiment extremes. Instinctively fades crowded trades and enjoys being the last one out at tops.',
    bias: 'Status Quo Bias',
    bias_mechanics: 'contrarian',
    initial_stance: 0.25,
  },
  {
    id: 'clara',
    name: 'Clara C.',
    role: 'Social Trader',
    persona: 'Active on FinTwit and Discord, runs a copy-trading portfolio that tracks the wisdom of her network. Heavily influenced by what her peers are doing.',
    bias: 'Bandwagon Effect',
    bias_mechanics: 'bandwagon',
    initial_stance: 0.45,
  },
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

// Keyed by agent.bias_mechanics — maps each canonical bias to 3 reasoning
// templates the mock uses to populate per-tick reasoning strings.
const REASONINGS = {
  loss_aversion: [
    'Risk of loss outweighs potential gain at current levels.',
    'Preserving capital is the priority given the uncertainty.',
    'The downside scenario looks more probable than upside.',
  ],
  anchoring: [
    'Fundamentals anchor me near fair value despite short-term noise.',
    'My valuation model still points to the same level.',
    'Group sentiment is overreacting — my anchor holds.',
  ],
  optimism: [
    'Momentum is shifting — I see the upside developing.',
    'The opportunity outweighs the risk I\'m reading here.',
    'Trend is constructive; positioning accordingly.',
  ],
  contrarian: [
    'Everyone is moving one way, so I see opportunity the other.',
    'Contrarian signal: group consensus is too strong.',
    'The herd is wrong here — my instinct says opposite.',
  ],
  bandwagon: [
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

      // Tick math keyed off the agent's canonical bias_mechanics so demo
      // dynamics stay stable even if the display bias label changes.
      switch (agent.bias_mechanics) {
        case 'loss_aversion':
          delta = (aggregate - prev) * 0.10 - 0.012 + noise
          break
        case 'anchoring':
          delta = (agent.initial_stance - prev) * 0.15 + (aggregate - prev) * 0.06 + noise * 0.6
          break
        case 'optimism':
          delta = (aggregate - prev) * 0.32 + noise
          break
        case 'contrarian':
          delta = (prev - aggregate) * 0.20 + noise * 1.4
          break
        default:
          // bandwagon and anything else: moderate pull toward the aggregate
          delta = (aggregate - prev) * 0.22 + noise
      }

      const newStance = Math.round(clamp(prev + delta, 0.05, 0.95) * 1000) / 1000
      stances[agent.id] = newStance

      const reasonings = REASONINGS[agent.bias_mechanics] || REASONINGS.bandwagon
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
 * Build the synthetic done-event payload: decision summary + influence graph
 * + methodology. Derived from the generated ticks so the numbers are
 * self-consistent with what the user just watched.
 */
function buildDoneResult(ticks, agents, runId) {
  const finalTick = ticks[ticks.length - 1]
  const finalAgg = finalTick?.aggregate_stance ?? 0.5
  const finalStances = {}
  if (finalTick) {
    finalTick.events.forEach(e => { finalStances[e.agent_id] = e.stance })
  }

  // Confidence heuristic matching the backend's: stance spread + distance
  // from neutral. The demo consistently produces a moderate-consensus read.
  const stanceValues = Object.values(finalStances)
  const mean = stanceValues.reduce((s, v) => s + v, 0) / Math.max(stanceValues.length, 1)
  const sigma = Math.sqrt(
    stanceValues.reduce((s, v) => s + (v - mean) ** 2, 0) / Math.max(stanceValues.length, 1),
  )
  const leaning = Math.abs(mean - 0.5)
  let confidence = 'moderate'
  if (sigma < 0.10 && leaning > 0.15) confidence = 'high'
  else if (sigma > 0.22) confidence = 'polarized'
  else if (leaning < 0.08) confidence = 'low'

  const agentById = Object.fromEntries(agents.map(a => [a.id, a]))
  const ranked = [...agents].sort(
    (a, b) => (finalStances[b.id] ?? 0.5) - (finalStances[a.id] ?? 0.5),
  )
  const top = ranked.slice(0, 2)
  const bottom = ranked.slice(-2).reverse()

  const positionLabel = (stance) => {
    if (stance >= 0.75) return 'Strong Buy'
    if (stance >= 0.55) return 'Accumulate'
    if (stance >= 0.45) return 'Hold'
    if (stance >= 0.25) return 'Reduce'
    return 'Strong Sell'
  }

  const arg = (agent, reasoning) => ({
    agent_name: agent.name,
    agent_role: agent.role,
    position: positionLabel(finalStances[agent.id] ?? 0.5),
    reasoning,
  })

  const decisionSummary = {
    verdict: `The panel leans cautiously toward accumulating on this Fed rate decision, with institutional and momentum voices converging above neutral while the retail and contrarian camps hold back — meaning the move has support but isn't a crowded trade.`,
    verdict_stance: finalAgg,
    confidence,
    confidence_rationale: `σ=${sigma.toFixed(2)} with ${leaning > 0.12 ? 'a clear' : 'a modest'} lean above neutral (agg ${finalAgg.toFixed(2)}). ${confidence === 'moderate' ? 'Disagreement persists, but the direction is consistent.' : confidence === 'high' ? 'Tight alignment on direction.' : 'Dispersion is wide.'}`,
    arguments_for: [
      arg(
        top[0] ?? ranked[0],
        `${(top[0] ?? ranked[0]).bias} leads ${(top[0] ?? ranked[0]).name.split(' ')[0]} to follow the post-decision drift and add exposure while volatility is fading.`,
      ),
      arg(
        top[1] ?? ranked[1],
        `${(top[1] ?? ranked[1]).name.split(' ')[0]}'s ${(top[1] ?? ranked[1]).bias.toLowerCase()} keeps them anchored above fair value after the Fed's signal stabilized rates expectations.`,
      ),
    ],
    arguments_against: [
      arg(
        bottom[0] ?? ranked[ranked.length - 1],
        `${(bottom[0] ?? ranked[ranked.length - 1]).bias} pulls ${(bottom[0] ?? ranked[ranked.length - 1]).name.split(' ')[0]} toward capital preservation — the downside risk from any surprise in forward guidance dominates the upside.`,
      ),
      arg(
        bottom[1] ?? ranked[ranked.length - 2],
        `${(bottom[1] ?? ranked[ranked.length - 2]).name.split(' ')[0]} fades the consensus on principle: when everyone is buying the rate cut, that's usually the top.`,
      ),
    ],
    key_risk: `Persistent inflation surprises in the next CPI print would invalidate the panel's "rates-peak" read. Retail Rachel raised this and nobody disputed the mechanism — it's the live downside that the consensus is papering over.`,
    what_could_change: `A single hotter-than-expected inflation release, or a hawkish FOMC minutes revision, would flip Ivan and Elias back below neutral within a tick or two and wipe out the current lean. Conversely, softer PCE data locks in the "accumulate" read.`,
    actionable_takeaways: [
      'Set a conditional size-up: add on a soft PCE, trim on any hot CPI print.',
      'Watch the Fed speakers calendar for hawkish dissent that could re-anchor Ivan.',
      'Treat Pete\'s contrarian signal as a volatility hedge, not a directional view.',
      'Position size for moderate — not high — confidence; don\'t over-commit.',
    ],
    influence_narrative: `Institutional Ivan set the anchor at the open and held it; his valuation-driven conviction pulled Elias and Clara toward support as the session progressed. Pete stayed contrarian throughout — his reactance kept the panel from converging too tightly. Rachel's loss aversion resisted the drift but didn't break it. The result is a real, earned lean rather than a herd bounce.`,
    herd_moments: [
      'Tick 11: three agents converged toward accumulate within the same tick after Ivan reiterated his fair-value anchor — worth flagging as a brief bandwagon moment, but the move held through subsequent ticks.',
    ],
    grounded_reasoning_rates: {},
  }

  // Influence graph — a small set of believable edges + one herd_pressure
  // to exercise the AgentDetail Influences tab and make the judge's
  // herd_moment concrete.
  const edges = [
    {
      tick: 3,
      source_id: 'ivan',
      target_id: 'elias',
      message: 'Valuation holds — I\'m adding here.',
      target_stance_before: 0.55,
      target_stance_after: 0.59,
      influence_delta: 0.04,
      edge_type: 'explicit_message',
    },
    {
      tick: 5,
      source_id: 'elias',
      target_id: 'clara',
      message: 'Momentum is confirming Ivan\'s anchor.',
      target_stance_before: 0.46,
      target_stance_after: 0.50,
      influence_delta: 0.04,
      edge_type: 'explicit_message',
    },
    {
      tick: 8,
      source_id: 'pete',
      target_id: 'rachel',
      message: 'Consensus is crowded — I\'m cautious here.',
      target_stance_before: 0.34,
      target_stance_after: 0.31,
      influence_delta: -0.03,
      edge_type: 'explicit_message',
    },
    {
      tick: 11,
      source_id: '__aggregate__',
      target_id: 'clara',
      message: '(herd pressure — aggregate lifted Clara toward consensus)',
      target_stance_before: 0.52,
      target_stance_after: 0.58,
      influence_delta: 0.06,
      edge_type: 'herd_pressure',
    },
    {
      tick: 14,
      source_id: 'ivan',
      target_id: 'rachel',
      message: 'If the data holds, downside is limited here.',
      target_stance_before: 0.32,
      target_stance_after: 0.35,
      influence_delta: 0.03,
      edge_type: 'explicit_message',
    },
  ]

  const methodology = {
    agent_count: agents.length,
    tick_count: ticks.length,
    agents_per_role: agents.reduce((acc, a) => {
      acc[a.role] = (acc[a.role] || 0) + 1
      return acc
    }, {}),
    biases_assigned: Object.fromEntries(agents.map(a => [a.id, a.bias])),
    ensemble_size: 1,
    seed: 42,
    // Match the live backend keys (src/pythia/confidence.py) so the demo's
    // Oracle's Method panel is an honest preview of a real run's panel.
    confidence_thresholds: {
      agreement_clustered_max: 0.10,
      agreement_mixed_max: 0.20,
      conviction_tepid_max: 0.10,
      conviction_moderate_max: 0.20,
    },
    llm_provider: 'demo',
    llm_model: 'deterministic-mock',
  }

  return {
    run_id: runId,
    decision_summary: decisionSummary,
    influence_graph: { edges, nodes: [] },
    methodology,
  }
}

/**
 * Replay a mock simulation by emitting SSE-equivalent events via onEvent.
 * Returns a cancel function — call it to abort mid-demo.
 */
export function startDemoStream(onEvent) {
  const ticks = generateDemoTicks(DEMO_AGENTS, DEMO_SCENARIO_META.tick_count)
  const runId = `demo_${Date.now()}`
  const doneResult = buildDoneResult(ticks, DEMO_AGENTS, runId)
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

  // done → carries decision summary, influence graph, methodology. Emitted
  // slightly after the last tick would render visually, so the verdict
  // appears when the playback finishes rather than instantly.
  const doneAt = 2100 + ticks.length * 80 + (DEMO_SCENARIO_META.tick_count * 2300) + 600
  after(doneAt, () => onEvent({ type: 'done', data: doneResult }))

  return () => {
    cancelled = true
    ids.forEach(clearTimeout)
  }
}
