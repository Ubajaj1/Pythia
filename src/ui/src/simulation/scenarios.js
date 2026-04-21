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

const AGENT_COLORS = [
  { color: '#B8907A', glow: 'rgba(184,144,122,0.32)' },
  { color: '#7A9BA8', glow: 'rgba(122,155,168,0.32)' },
  { color: '#A09B7A', glow: 'rgba(160,155,122,0.32)' },
  { color: '#C08878', glow: 'rgba(192,136,120,0.32)' },
  { color: '#8A9B8A', glow: 'rgba(138,155,138,0.32)' },
  { color: '#9B8AA0', glow: 'rgba(155,138,160,0.32)' },
  { color: '#A0907A', glow: 'rgba(160,144,122,0.32)' },
  { color: '#7AA09B', glow: 'rgba(122,160,155,0.32)' },
  { color: '#8A7A9B', glow: 'rgba(138,122,155,0.32)' },
  { color: '#9BA07A', glow: 'rgba(155,160,122,0.32)' },
]

export function scenarioFromRunResult(result) {
  const protagonists = result.agents.map((agent, i) => ({
    id: agent.id,
    name: agent.name,
    trait: agent.bias,
    color: AGENT_COLORS[i % AGENT_COLORS.length].color,
    glow: AGENT_COLORS[i % AGENT_COLORS.length].glow,
  }))

  const amendments = result.agents.map(agent => [
    'Recalibrating',
    `${agent.bias} parameters...`,
  ])

  return {
    name: result.scenario.title,
    protagonists,
    amendments,
    ticks: result.ticks,
    agents: result.agents,
  }
}

export function scenarioFromOracleResult(oracleResult) {
  const firstRun = oracleResult.runs[0]
  const amendedIds = new Set(firstRun.amended_agent_ids)

  const protagonists = firstRun.result.agents.map((agent, i) => ({
    id: agent.id,
    name: agent.name,
    trait: agent.bias,
    color: AGENT_COLORS[i % AGENT_COLORS.length].color,
    glow: AGENT_COLORS[i % AGENT_COLORS.length].glow,
    amended: amendedIds.has(agent.id),
  }))

  const amendments = firstRun.result.agents.map(agent => [
    amendedIds.has(agent.id) ? 'Amending' : 'Recalibrating',
    `${agent.bias} rules...`,
  ])

  return {
    name: firstRun.result.scenario.title,
    protagonists,
    amendments,
    ticks: firstRun.result.ticks,
    agents: firstRun.result.agents,
    coherenceHistory: oracleResult.coherence_history.map(s => Math.round(s * 100)),
  }
}
