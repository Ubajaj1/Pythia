import { useSimulation } from './simulation/useSimulation'
import { getScenario } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'

const SCENARIO_ID = 'market-sentiment'

export default function App() {
  const scenario = getScenario(SCENARIO_ID)

  const sim = useSimulation(scenario.protagonists, scenario.amendments)

  const templeProtagonist = sim.templeIdx !== null
    ? scenario.protagonists[sim.templeIdx]
    : null

  const templeAmendment = sim.templeIdx !== null
    ? scenario.amendments[sim.templeIdx]
    : ['', '']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Header
        scenarioName={scenario.name}
        tick={sim.tick}
        run={sim.run}
        progressPercent={sim.progressPercent}
        onRestart={sim.restart}
      />

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Stage
          protagonists={scenario.protagonists}
          protoStates={sim.protoStates}
        />
        <Arena
          crowdStateIndex={sim.crowdStateIndex}
          crowdStateName={sim.crowdStateName}
        />
        <Temple
          protagonist={templeProtagonist}
          amendment={templeAmendment}
        />
      </div>

      <AccuracyCurve history={sim.accuracyHistory} />
    </div>
  )
}
