import { useState, useRef } from 'react'
import { useApiSimulation, useOracleSimulation, useStreamingSimulation } from './simulation/useSimulation'
import { scenarioFromRunResult, scenarioFromOracleResult, scenarioFromStreamScenario, scenarioFromEnsembleResult } from './simulation/scenarios'
import Header         from './components/Header'
import Stage          from './components/Stage'
import Arena          from './components/Arena'
import Temple         from './components/Temple'
import AccuracyCurve  from './components/AccuracyCurve'
import StanceGraph    from './components/StanceGraph'
import InputBar       from './components/InputBar'
import DecisionPanel  from './components/DecisionPanel'
import AgentDetail    from './components/AgentDetail'
import OracleMethod   from './components/OracleMethod'

const SAMPLE_SCENARIOS = [
  "Should our startup adopt AI coding tools for all engineering tasks?",
  "Should we raise a Series A or stay bootstrapped and grow profitably?",
  "Should a city ban single-use plastics in restaurants?",
  "Should tech companies mandate a return to the office 5 days a week?",
  "Should a social media platform ban political advertising entirely?",
]

const btnBase = {
  background: 'transparent',
  border: '1px solid #6a6a60',
  color: '#FFFFFF',
  borderRadius: '4px',
  padding: '11px 20px',
  fontFamily: 'Syne, sans-serif',
  fontSize: '14px',
  cursor: 'pointer',
  textAlign: 'left',
  lineHeight: 1.55,
}

function LandingScreen({ onSelectScenario }) {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 30,
      padding: '40px 60px',
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'Playfair Display, serif',
          fontStyle: 'italic',
          fontSize: 56,
          color: '#FFFFFF',
          lineHeight: 1.3,
          paddingBottom: '0.12em',
        }}>Pythia</div>
        <div style={{
          fontFamily: 'Syne, sans-serif',
          fontWeight: 400,
          fontSize: 16,
          color: '#FFFFFF',
          marginTop: 12,
          letterSpacing: '0.06em',
          lineHeight: 1.5,
        }}>Describe a decision. Watch the world respond.</div>
      </div>

      <div style={{ width: 40, height: 1, background: '#6a6a60' }} />

      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color: '#FFFFFF',
          marginBottom: 16,
        }}>Try one of these scenarios</div>
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '10px',
          justifyContent: 'center',
          maxWidth: 740,
        }}>
          {SAMPLE_SCENARIOS.map((s, i) => (
            <button
              key={i}
              onClick={() => onSelectScenario(s)}
              style={btnBase}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = '#F5D98A'
                e.currentTarget.style.color = '#F5D98A'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = '#6a6a60'
                e.currentTarget.style.color = '#FFFFFF'
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

function SimulationView({ scenario, sim, decisionSummary, influenceGraph, selectedAgentId, onAgentClick, onCloseAgent, mode, ensembleResult, backtestResult, methodology, runId, onHome, streamTicks }) {
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
        totalTicks={scenario.tickCount || scenario.ticks?.length || 20}
        onHome={onHome}
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
            agentNames={agentNames}
          />
        )}
        <Arena
          crowdStateIndex={sim.crowdStateIndex}
          crowdStateName={sim.crowdStateName}
          aggregateStance={aggregateStance}
        />
        <Temple protagonist={templeProtagonist} amendment={templeAmendment} />
      </div>
      <OracleMethod methodology={methodology} runId={runId} />
      {/* StanceGraph always visible in single-run mode — persists after verdict arrives.
          For streaming/demo the ticks live in streamTicks, not scenario.ticks. */}
      {(() => {
        const graphTicks = scenario.ticks?.length > 0 ? scenario.ticks : (streamTicks || [])
        if (mode === 'oracle' || graphTicks.length === 0) return null
        return (
          <StanceGraph
            ticks={graphTicks}
            agents={scenario.protagonists}
            stanceSpectrum={scenario.stanceSpectrum}
            currentTick={sim.tick}
          />
        )
      })()}
      {decisionSummary ? (
        <DecisionPanel
          decisionSummary={decisionSummary}
          stanceSpectrum={scenario.stanceSpectrum}
          ensembleResult={ensembleResult}
          backtestResult={backtestResult}
        />
      ) : mode === 'oracle' ? (
        <AccuracyCurve history={sim.accuracyHistory} />
      ) : (scenario.ticks?.length === 0 && (!streamTicks || streamTicks.length === 0)) ? (
        <div style={{
          height: 60,
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#FFFFFF',
        }}>
          Awaiting first tick…
        </div>
      ) : null}
    </>
  )
}

function ApiSimulation({ runResult, selectedAgentId, onAgentClick, onCloseAgent, backtestResult, onHome }) {
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
      mode="single"
      backtestResult={backtestResult}
      methodology={runResult.methodology}
      runId={runResult.run_id}
      onHome={onHome}
    />
  )
}

function OracleSimulation({ oracleResult, selectedAgentId, onAgentClick, onCloseAgent, onHome }) {
  const scenario = scenarioFromOracleResult(oracleResult)
  const sim = useOracleSimulation(scenario)
  const firstRun = oracleResult.runs?.[0]
  return (
    <SimulationView
      scenario={scenario}
      sim={sim}
      decisionSummary={oracleResult.decision_summary}
      influenceGraph={oracleResult.influence_graph}
      selectedAgentId={selectedAgentId}
      onAgentClick={onAgentClick}
      onCloseAgent={onCloseAgent}
      mode="oracle"
      methodology={firstRun?.result?.methodology}
      runId={firstRun?.result?.run_id}
      onHome={onHome}
    />
  )
}

function EnsembleRunSelector({ ensembleResult, activeRunIdx, onSelectRun }) {
  const mono = { fontFamily: 'var(--font-mono)' }
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '6px 28px',
      background: '#0f0f0d',
      borderBottom: '1px solid #1a1a17',
    }}>
      <span style={{
        ...mono,
        fontSize: 9,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        color: '#FFFFFF',
      }}>
        Ensemble Runs
      </span>
      {ensembleResult.runs.map((r, i) => {
        const active = i === activeRunIdx
        const agg = r.summary?.final_aggregate_stance
        const conf = r.decision_summary?.confidence || '—'
        return (
          <button
            key={i}
            type="button"
            onClick={() => onSelectRun(i)}
            style={{
              ...mono,
              fontSize: 10,
              padding: '3px 9px',
              borderRadius: 2,
              border: active ? '1px solid #6A9B6A' : '1px solid #6a6a60',
              background: active ? 'rgba(106,155,106,0.1)' : 'transparent',
              color: active ? '#8FD18F' : '#FFFFFF',
              cursor: 'pointer',
            }}
          >
            Run {i + 1}
            <span style={{ marginLeft: 6, opacity: 0.9 }}>
              {agg != null ? agg.toFixed(2) : '—'}
            </span>
            <span style={{ marginLeft: 6, opacity: 0.85, fontSize: 9 }}>
              {conf}
            </span>
          </button>
        )
      })}
      <span style={{
        ...mono,
        fontSize: 9,
        color: '#FFFFFF',
        marginLeft: 'auto',
      }}>
        {ensembleResult.ensemble_size} runs · agreement {Math.round((ensembleResult.agreement_ratio || 0) * 100)}%
      </span>
    </div>
  )
}

function EnsembleSimulation({ ensembleResult, selectedAgentId, onAgentClick, onCloseAgent, onHome }) {
  const [activeRunIdx, setActiveRunIdx] = useState(0)
  const activeRun = ensembleResult.runs[activeRunIdx] || ensembleResult.primary_run || ensembleResult.runs?.[0]
  // Build a scenario from the ACTIVE run, not just the primary — so the user can
  // replay any of the N runs' ticks and see its agents' trajectories.
  const scenario = scenarioFromRunResult(activeRun)
  const sim = useApiSimulation(scenario)
  return (
    <>
      <EnsembleRunSelector
        ensembleResult={ensembleResult}
        activeRunIdx={activeRunIdx}
        onSelectRun={setActiveRunIdx}
      />
      <SimulationView
        scenario={scenario}
        sim={sim}
        decisionSummary={activeRun?.decision_summary}
        influenceGraph={activeRun?.influence_graph}
        selectedAgentId={selectedAgentId}
        onAgentClick={onAgentClick}
        onCloseAgent={onCloseAgent}
        mode="single"
        ensembleResult={ensembleResult}
        methodology={activeRun?.methodology}
        runId={activeRun?.run_id}
        onHome={onHome}
      />
    </>
  )
}

function StreamingSimulation({ scenario, ticksRef, doneResult, selectedAgentId, onAgentClick, onCloseAgent, onHome }) {
  const sim = useStreamingSimulation(scenario, ticksRef)
  // `ticksRef.current` is mutated imperatively by the SSE handler; sim.tick
  // ticks up once per TICK_MS and triggers a re-render. Slice up to the
  // currently-visible tick so StanceGraph only shows what we've revealed.
  const visibleTicks = ticksRef.current.slice(0, Math.max(sim.tick, 0))
  return (
    <SimulationView
      scenario={scenario}
      sim={sim}
      decisionSummary={doneResult?.decision_summary}
      influenceGraph={doneResult?.influence_graph}
      selectedAgentId={selectedAgentId}
      onAgentClick={onAgentClick}
      onCloseAgent={onCloseAgent}
      mode="single"
      methodology={doneResult?.methodology}
      runId={doneResult?.run_id}
      onHome={onHome}
      streamTicks={visibleTicks}
    />
  )
}

function ThinkingLayout({ title, onHome }) {
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
        onHome={onHome}
      />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Stage protagonists={[]} protoStates={[]} loading={true} />
        <Arena crowdStateIndex={0} crowdStateName="Herd Neutrality" />
        <Temple protagonist={null} amendment={['', '']} />
      </div>
      {/* Status strip — no fake chart while we're still thinking */}
      <div style={{
        height: 60,
        borderTop: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        padding: '0 28px',
        flexShrink: 0,
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: '#F5D98A',
          boxShadow: '0 0 8px rgba(245,217,138,0.55)',
          animation: 'pulse 1.2s ease-in-out infinite',
        }} />
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#FFFFFF',
        }}>
          The Oracle is preparing the panel…
        </div>
      </div>
    </>
  )
}

export default function App() {
  const [runResult, setRunResult] = useState(null)
  const [oracleResult, setOracleResult] = useState(null)
  const [ensembleResult, setEnsembleResult] = useState(null)
  const [backtestResult, setBacktestResult] = useState(null)
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

  function handleHome() {
    setRunResult(null)
    setOracleResult(null)
    setEnsembleResult(null)
    setBacktestResult(null)
    setStreamScenario(null)
    setStreamPhase(null)
    setStreamTitle('')
    setStreamDoneResult(null)
    streamTicksRef.current = []
    setSelectedAgentId(null)
    setPrefillPrompt('')
    setIsLoading(false)
  }

  function handleOracleResult(result) {
    setStreamScenario(null)
    setStreamPhase(null)
    setStreamDoneResult(null)
    setRunResult(null)
    setEnsembleResult(null)
    setOracleResult(result)
    setSelectedAgentId(null)
  }

  function handleEnsembleResult(result) {
    setStreamScenario(null)
    setStreamPhase(null)
    setStreamDoneResult(null)
    setRunResult(null)
    setOracleResult(null)
    setBacktestResult(null)
    setEnsembleResult(result)
    setSelectedAgentId(null)
  }

  function handleBacktestResult(result) {
    setStreamScenario(null)
    setStreamPhase(null)
    setStreamDoneResult(null)
    setOracleResult(null)
    setEnsembleResult(null)
    // result has { run: RunResultWithInsights, backtest: BacktestResult }
    setRunResult(result.run)
    setBacktestResult(result.backtest)
    setSelectedAgentId(null)
  }

  function handleStreamEvent(event) {
    if (event.type === 'thinking') {
      streamTicksRef.current = []
      setRunResult(null)
      setOracleResult(null)
      setEnsembleResult(null)
      setBacktestResult(null)
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
        onEnsembleResult={handleEnsembleResult}
        onBacktestResult={handleBacktestResult}
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
          onHome={handleHome}
        />
      ) : streamPhase === 'thinking' ? (
        <ThinkingLayout title={streamTitle} onHome={handleHome} />
      ) : isLoading ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#F5D98A', fontFamily: 'Playfair Display, serif', fontSize: '18px',
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
          onHome={handleHome}
        />
      ) : ensembleResult ? (
        <EnsembleSimulation
          ensembleResult={ensembleResult}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onCloseAgent={handleCloseAgent}
          onHome={handleHome}
        />
      ) : runResult ? (
        <ApiSimulation
          runResult={runResult}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onCloseAgent={handleCloseAgent}
          backtestResult={backtestResult}
          onHome={handleHome}
        />
      ) : (
        <LandingScreen onSelectScenario={handleSelectScenario} />
      )}
    </div>
  )
}
