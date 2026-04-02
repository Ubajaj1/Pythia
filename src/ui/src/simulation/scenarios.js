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
