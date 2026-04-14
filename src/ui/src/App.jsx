import { useState } from 'react'
import { useSimulation, useApiSimulation } from './simulation/useSimulation'
import { getScenario, scenarioFromRunResult } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'
import InputBar       from './components/InputBar'

const DEFAULT_SCENARIO_ID = 'market-sentiment'

function SimulationView({ scenario, sim }) {
  const templeProtagonist = sim.templeIdx !== null
    ? scenario.protagonists[sim.templeIdx]
    : null

  const templeAmendment = sim.templeIdx !== null
    ? scenario.amendments[sim.templeIdx]
    : ['', '']

  return (
    <>
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
    </>
  )
}

function MockSimulation() {
  const scenario = getScenario(DEFAULT_SCENARIO_ID)
  const sim = useSimulation(scenario.protagonists, scenario.amendments)
  return <SimulationView scenario={scenario} sim={sim} />
}

function ApiSimulation({ runResult }) {
  const scenario = scenarioFromRunResult(runResult)
  const sim = useApiSimulation(scenario)
  return <SimulationView scenario={scenario} sim={sim} />
}

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <InputBar
        onSimulationResult={setRunResult}
        isLoading={isLoading}
        setIsLoading={setIsLoading}
      />
      {isLoading ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A88C52', fontFamily: 'Playfair Display, serif', fontSize: '18px',
          fontStyle: 'italic',
        }}>
          The Oracle is deliberating...
        </div>
      ) : runResult ? (
        <ApiSimulation runResult={runResult} />
      ) : (
        <MockSimulation />
      )}
    </div>
  )
}
