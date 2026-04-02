import { describe, it, expect } from 'vitest'
import { CROWD_STATES, getScenario } from './scenarios'

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
