// Drives a saved run through the crowd classifier to print tick-by-tick labels.
// Usage: node scripts/check-crowd-labels.mjs <path-to-run.json>
import fs from 'fs'
import path from 'path'
import { classifyCrowdState } from '../src/simulation/crowdState.js'

const file = process.argv[2] || '../../data/runs/run_2026-04-29_043335_35eedb.json'
const full = path.resolve(file)
const r = JSON.parse(fs.readFileSync(full, 'utf8'))
const edges = r.influence_graph?.edges || []

console.log(`Run: ${r.run_id}`)
console.log(`Scenario: ${r.scenario?.title}`)
console.log(`Ticks: ${r.ticks.length}`)
console.log('')
console.log('Tick | State       | σ     | spread | Δagg  | agg')
console.log('-----|-------------|-------|--------|-------|------')

for (let t = 1; t <= r.ticks.length; t++) {
  const tick = r.ticks[t - 1]
  const stances = tick.events.map(e => e.stance)
  const mean = stances.reduce((s, v) => s + v, 0) / stances.length
  const sigma = Math.sqrt(stances.reduce((s, v) => s + (v - mean) ** 2, 0) / stances.length)
  const spread = Math.max(...stances) - Math.min(...stances)
  const prev = t > 1 ? r.ticks[t - 2].aggregate_stance : tick.aggregate_stance
  const dagg = Math.abs(tick.aggregate_stance - prev)
  const { name } = classifyCrowdState(r.ticks, t, edges)
  console.log(
    `  ${String(t).padStart(2)} | ${name.padEnd(11)} | ${sigma.toFixed(3)} | ${spread.toFixed(3)}  | ${dagg.toFixed(3)} | ${tick.aggregate_stance.toFixed(3)}`,
  )
}
