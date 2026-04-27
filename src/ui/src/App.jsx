import { useState, useRef } from 'react'
import { useApiSimulation, useOracleSimulation, useStreamingSimulation } from './simulation/useSimulation'
import { scenarioFromRunResult, scenarioFromOracleResult, scenarioFromStreamScenario } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'
import InputBar       from './components/InputBar'
import DecisionPanel  from './components/DecisionPanel'
import AgentDetail    from './components/AgentDetail'

const SAMPLE_SCENARIOS = [
  "Should our startup adopt AI coding tools for all engineering tasks?",
  "Should we raise a Series A or stay bootstrapped and grow profitably?",
  "Should a city ban single-use plastics in restaurants?",
  "Should tech companies mandate a return to the office 5 days a week?",
  "Should a social media platform ban political advertising entirely?",
]

const btnBase = {
  background: 'transparent',
  border: '1px solid #2a2a25',
  color: '#7a7a6a',
  borderRadius: '3px',
  padding: '7px 16px',
  fontFamily: 'Syne, sans-serif',
  fontSize: '11px',
  cursor: 'pointer',
  textAlign: 'left',
  lineHeight: 1.5,
}

function LandingScreen({ onSelectScenario }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 28,
      padding: '40px 60px',
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'Playfair Display, serif',
          fontStyle: 'italic',
          fontSize: 38,
          color: '#d4c9a8',
        }}>Pythia</div>
        <div style={{
          fontFamily: 'Syne, sans-serif',
          fontWeight: 300,
          fontSize: 13,
          color: '#4a4a44',
          marginTop: 10,
          letterSpacing: '0.06em',
        }}>Describe a decision. Watch the world respond.</div>
      </div>

      <div style={{ width: 36, height: 1, background: '#1a1a17' }} />

      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 8,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#3a3a35',
          marginBottom: 14,
        }}>Try one of these scenarios</div>
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '10px',
          justifyContent: 'center',
          maxWidth: 680,
        }}>
          {SAMPLE_SCENARIOS.map((s, i) => (
            <button
              key={i}
              onClick={() => onSelectScenario(s)}
              style={btnBase}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = '#A88C52'
                e.currentTarget.style.color = '#A88C52'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = '#2a2a25'
                e.currentTarget.style.color = '#7a7a6a'
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function SimulationView({ scenario, sim, decisionSummary, influenceGraph, selectedAgentId, onAgentClick, onCloseAgent }) {
  const templeProtagonist = sim.templeIdx !== null ? scenario.protagonists[sim.templeIdx] : null
  const templeAmendment = sim.templeIdx !== null ? scenario.amendments[sim.templeIdx] : ['', '']

  // Get the current aggregate stance from the latest tick data
  const aggregateStance = sim.aggregateStance ?? null

  // Build agent lookup for the detail panel
  const selectedAgent = selectedAgentId
    ? scenario.protagonists.find(p => p.id === selectedAgentId)
    : null
  const selectedAgentInfo = selectedAgentId && scenario.agents
    ? scenario.agents.find(a => a.id === selectedAgentId)
    : null

  // Get influence and trajectory data from the graph
  const agentInfluences = selectedAgentId && influenceGraph
    ? (influenceGraph.edges || []).filter(e => e.target_id === selectedAgentId)
    : []
  const agentTrajectory = selectedAgentId && influenceGraph
    ? (influenceGraph.nodes || []).filter(n => n.agent_id === selectedAgentId)
    : []

  // Build agent name map for influence display
  const agentNames = {}
  if (scenario.agents) {
    scenario.agents.forEach(a => { agentNames[a.id] = a.name })
  }
  scenario.protagonists.forEach(p => { agentNames[p.id] = p.name })

  return (
    <>
      <Header
        scenarioName={scenario.name}
        tick={sim.tick}
        run={sim.run}
        progressPercent={sim.progressPercent}
        onRestart={sim.restart}
        paused={sim.paused}
        onTogglePause={sim.togglePause}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0, position: 'relative' }}>
        <Stage
          protagonists={scenario.protagonists}
          protoStates={sim.protoStates}
          selectedAgentId={selectedAgentId}
          onAgentClick={onAgentClick}
        />
        {selectedAgent && (
          <AgentDetail
            agent={selectedAgent}
            agentInfo={selectedAgentInfo}
            influences={agentInfluences}
            trajectory={agentTrajectory}
            spectrum={scenario.stanceSpectrum}
            onClose={onCloseAgent}
          />
        )}
        <Arena
          crowdStateIndex={sim.crowdStateIndex}
          crowdStateName={sim.crowdStateName}
          aggregateStance={aggregateStance}
        />
        <Temple protagonist={templeProtagonist} amendment={templeAmendment} />
      </div>
      {decisionSummary ? (
        <DecisionPanel
          decisionSummary={decisionSummary}
          stanceSpectrum={scenario.stanceSpectrum}
        />
      ) : (
        <AccuracyCurve history={sim.accuracyHistory} />
      )}
    </>
  )
}

function ApiSimulation({ runResult, selectedAgentId, onAgentClick, onCloseAgent }) {
  const scenario = scenarioFromRunResult(runResult)
  const sim = useApiSimulation(scenario)
  return (
    <SimulationView
      scenario={scenario}
      sim={sim}
      decisionSummary={runResult.decision_summary}
      influenceGraph={runResult.influence_graph}
      selectedAgentId={selectedAgentId}
      onAgentClick={onAgentClick}
      onCloseAgent={onCloseAgent}
    />
  )
}

function OracleSimulation({ oracleResult, selectedAgentId, onAgentClick, onCloseAgent }) {
  const scenario = scenarioFromOracleResult(oracleResult)
  const sim = useOracleSimulation(scenario)
  return (
    <SimulationView
      scenario={scenario}
      sim={sim}
      decisionSummary={oracleResult.decision_summary}
      influenceGraph={oracleResult.influence_graph}
      selectedAgentId={selectedAgentId}
      onAgentClick={onAgentClick}
      onCloseAgent={onCloseAgent}
    />
  )
}

function StreamingSimulation({ scenario, ticksRef, doneResult, selectedAgentId, onAgentClick, onCloseAgent }) {
  const sim = useStreamingSimulation(scenario, ticksRef)
  return (
    <SimulationView
      scenario={scenario}
      sim={sim}
      decisionSummary={doneResult?.decision_summary}
      influenceGraph={doneResult?.influence_graph}
      selectedAgentId={selectedAgentId}
      onAgentClick={onAgentClick}
      onCloseAgent={onCloseAgent}
    />
  )
}

function ThinkingLayout({ title }) {
  return (
    <>
      <Header
        scenarioName={title || 'Summoning advisors…'}
        tick={0}
        run={1}
        progressPercent={0}
        onRestart={() => {}}
        paused={false}
        onTogglePause={() => {}}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Stage protagonists={[]} protoStates={[]} loading={true} />
        <Arena crowdStateIndex={0} crowdStateName="Herd Neutrality" />
        <Temple protagonist={null} amendment={['', '']} />
      </div>
      <AccuracyCurve history={[44]} />
    </>
  )
}

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [oracleResult, setOracleResult] = useState(null)
  const [streamScenario, setStreamScenario] = useState(null)
  const [streamPhase, setStreamPhase] = useState(null)
  const [streamTitle, setStreamTitle] = useState('')
  const [streamDoneResult, setStreamDoneResult] = useState(null)
  const streamTicksRef = useRef([])
  const [isLoading, setIsLoading] = useState(false)
  const [prefillPrompt, setPrefillPrompt] = useState('')
  const [selectedAgentId, setSelectedAgentId] = useState(null)

  function handleAgentClick(agentId) {
    setSelectedAgentId(prev => prev === agentId ? null : agentId)
  }

  function handleCloseAgent() {
    setSelectedAgentId(null)
  }

  function handleOracleResult(result) {
    setStreamScenario(null)
    setStreamPhase(null)
    setStreamDoneResult(null)
    setRunResult(null)
    setOracleResult(result)
    setSelectedAgentId(null)
  }

  function handleStreamEvent(event) {
    if (event.type === 'thinking') {
      streamTicksRef.current = []
      setRunResult(null)
      setOracleResult(null)
      setStreamScenario(null)
      setStreamTitle('')
      setStreamDoneResult(null)
      setStreamPhase('thinking')
      setSelectedAgentId(null)
    } else if (event.type === 'blueprint') {
      setStreamTitle(event.data.title)
    } else if (event.type === 'scenario') {
      setStreamScenario(scenarioFromStreamScenario(event.data))
      setStreamPhase('ready')
    } else if (event.type === 'tick') {
      streamTicksRef.current.push(event.data)
    } else if (event.type === 'done') {
      setStreamDoneResult(event.data)
    }
  }

  function handleSelectScenario(scenario) {
    setPrefillPrompt(scenario)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <InputBar
        onOracleResult={handleOracleResult}
        onStreamEvent={handleStreamEvent}
        isLoading={isLoading}
        setIsLoading={setIsLoading}
        prefillPrompt={prefillPrompt}
      />
      {streamPhase === 'ready' && streamScenario ? (
        <StreamingSimulation
          scenario={streamScenario}
          ticksRef={streamTicksRef}
          doneResult={streamDoneResult}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onCloseAgent={handleCloseAgent}
        />
      ) : streamPhase === 'thinking' ? (
        <ThinkingLayout title={streamTitle} />
      ) : isLoading ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A88C52', fontFamily: 'Playfair Display, serif', fontSize: '18px',
          fontStyle: 'italic',
        }}>
          The Oracle is deliberating...
        </div>
      ) : oracleResult ? (
        <OracleSimulation
          oracleResult={oracleResult}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onCloseAgent={handleCloseAgent}
        />
      ) : runResult ? (
        <ApiSimulation
          runResult={runResult}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onCloseAgent={handleCloseAgent}
        />
      ) : (
        <LandingScreen onSelectScenario={handleSelectScenario} />
      )}
    </div>
  )
}
