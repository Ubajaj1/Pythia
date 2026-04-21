import { describe, it, expect } from 'vitest'
import { CROWD_STATES, getScenario, scenarioFromOracleResult } from './scenarios'

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

describe('scenarioFromOracleResult', () => {
  const mockRunResult = {
    run_id: 'oracle_test_r1',
    scenario: {
      input: 'test', type: 'market', title: 'Oracle Test',
      stance_spectrum: ['vb', 'b', 'n', 'bu', 'vbu'],
    },
    agents: [
      { id: 'a1', name: 'Agent One', role: 'trader', persona: 'p', bias: 'loss_aversion', initial_stance: 0.3 },
      { id: 'a2', name: 'Agent Two', role: 'analyst', persona: 'p', bias: 'anchoring', initial_stance: 0.7 },
    ],
    ticks: [],
    summary: {
      total_ticks: 0, final_aggregate_stance: 0.5,
      biggest_shift: { agent_id: 'a1', from: 0.3, to: 0.3, reason: '' },
      consensus_reached: false,
    },
  }

  const mockOracleResult = {
    prompt: 'test prompt',
    coherence_history: [0.5, 0.75, 1.0],
    runs: [{
      run_number: 1,
      result: mockRunResult,
      evaluations: [],
      coherence_score: 0.5,
      amended_agent_ids: ['a1'],
    }],
  }

  it('returns protagonists from first run agents', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.protagonists).toHaveLength(2)
    expect(scenario.protagonists[0].id).toBe('a1')
    expect(scenario.protagonists[1].id).toBe('a2')
  })

  it('marks amended agents with amended flag', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.protagonists[0].amended).toBe(true)   // a1 was amended
    expect(scenario.protagonists[1].amended).toBe(false)  // a2 was not
  })

  it('returns coherenceHistory scaled to 0-100', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.coherenceHistory).toEqual([50, 75, 100])
  })

  it('includes ticks from first run', () => {
    const scenario = scenarioFromOracleResult(mockOracleResult)
    expect(scenario.ticks).toBe(mockRunResult.ticks)
  })

  it('throws when runs array is empty', () => {
    expect(() => scenarioFromOracleResult({ prompt: 'test', coherence_history: [], runs: [] })).toThrow()
  })
})
