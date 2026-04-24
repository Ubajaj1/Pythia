import { useState } from 'react'
import { useSimulation, useApiSimulation, useOracleSimulation } from './simulation/useSimulation'
import { SCENARIOS, getScenario, scenarioFromRunResult, scenarioFromOracleResult } from './simulation/scenarios'
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

function MockSimulation({ scenarioId }) {
  const scenario = getScenario(scenarioId)
  const sim = useSimulation(scenario.protagonists, scenario.amendments)
  return <SimulationView scenario={scenario} sim={sim} />
}

function ApiSimulation({ runResult }) {
  const scenario = scenarioFromRunResult(runResult)
  const sim = useApiSimulation(scenario)
  return <SimulationView scenario={scenario} sim={sim} />
}

function OracleSimulation({ oracleResult }) {
  const scenario = scenarioFromOracleResult(oracleResult)
  const sim = useOracleSimulation(scenario)
  return <SimulationView scenario={scenario} sim={sim} />
}

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [oracleResult, setOracleResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedScenarioId, setSelectedScenarioId] = useState(DEFAULT_SCENARIO_ID)

  const isMockMode = !runResult && !oracleResult && !isLoading

  function handleSimulationResult(result) {
    setOracleResult(null)
    setRunResult(result)
  }

  function handleOracleResult(result) {
    setRunResult(null)
    setOracleResult(result)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <InputBar
        onSimulationResult={handleSimulationResult}
        onOracleResult={handleOracleResult}
        isLoading={isLoading}
        setIsLoading={setIsLoading}
      />
      {isMockMode && (
        <div style={{
          display: 'flex', gap: '8px', padding: '7px 20px',
          borderBottom: '1px solid #1a1a17', background: '#0D0D0B',
        }}>
          {Object.entries(SCENARIOS).map(([id, s]) => {
            const active = id === selectedScenarioId
            return (
              <button
                key={id}
                onClick={() => setSelectedScenarioId(id)}
                style={{
                  background: 'transparent',
                  border: `1px solid ${active ? '#A88C52' : '#2a2a25'}`,
                  color: active ? '#A88C52' : '#4a4a44',
                  borderRadius: '3px',
                  padding: '3px 12px',
                  fontFamily: 'Syne, sans-serif',
                  fontSize: '11px',
                  letterSpacing: '0.04em',
                  cursor: 'pointer',
                }}
              >
                {s.name.split(' — ')[0]}
              </button>
            )
          })}
        </div>
      )}
      {isLoading ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A88C52', fontFamily: 'Playfair Display, serif', fontSize: '18px',
          fontStyle: 'italic',
        }}>
          The Oracle is deliberating...
        </div>
      ) : oracleResult ? (
        <OracleSimulation oracleResult={oracleResult} />
      ) : runResult ? (
        <ApiSimulation runResult={runResult} />
      ) : (
        <MockSimulation scenarioId={selectedScenarioId} />
      )}
    </div>
  )
}
