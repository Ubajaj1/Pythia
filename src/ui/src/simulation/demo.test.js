import { describe, it, expect } from 'vitest'
import { demoVerdict } from './demo.js'

describe('demoVerdict', () => {
  it('describes selling when the aggregate is below neutral', () => {
    expect(demoVerdict(0.28)).toMatch(/selling/)
    expect(demoVerdict(0.28)).not.toMatch(/accumulat/)
  })
  it('describes accumulating when the aggregate is above neutral', () => {
    expect(demoVerdict(0.62)).toMatch(/accumulat/)
  })
  it('describes a split room near neutral', () => {
    expect(demoVerdict(0.5)).toMatch(/split/)
  })
})
