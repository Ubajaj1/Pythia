import { describe, it, expect } from 'vitest'
import { formatBias } from './format'

describe('formatBias', () => {
  it('maps canonical snake_case IDs to display names', () => {
    expect(formatBias('availability_heuristic')).toBe('Availability Heuristic')
    expect(formatBias('status_quo_bias')).toBe('Status Quo Bias')
    expect(formatBias('sunk_cost_fallacy')).toBe('Sunk Cost Fallacy')
    expect(formatBias('loss_aversion')).toBe('Loss Aversion')
    expect(formatBias('dunning_kruger')).toBe('Dunning-Kruger Effect')
    expect(formatBias('in_group_bias')).toBe('In-Group Bias')
  })

  it('returns already-formatted names unchanged', () => {
    expect(formatBias('Anchoring Bias')).toBe('Anchoring Bias')
    expect(formatBias('Loss Aversion')).toBe('Loss Aversion')
  })

  it('handles short canonical IDs', () => {
    expect(formatBias('anchoring')).toBe('Anchoring Bias')
    expect(formatBias('overconfidence')).toBe('Overconfidence Bias')
  })

  it('gracefully formats unknown snake_case strings', () => {
    expect(formatBias('mystery_new_bias')).toBe('Mystery New Bias')
  })

  it('leaves unknown already-spaced strings alone', () => {
    expect(formatBias('FOMO Drive')).toBe('FOMO Drive')
    expect(formatBias('Trend Chasing')).toBe('Trend Chasing')
  })

  it('handles empty / null / undefined defensively', () => {
    expect(formatBias('')).toBe('')
    expect(formatBias(null)).toBe('')
    expect(formatBias(undefined)).toBe('')
  })

  it('trims whitespace', () => {
    expect(formatBias('  anchoring  ')).toBe('Anchoring Bias')
  })
})
