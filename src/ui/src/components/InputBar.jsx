import { useState, useEffect, useRef } from 'react'
import { startDemoStream } from '../simulation/demo'

const API_BASE = ''

const PRESETS = [
  { id: 'auto',     label: 'Auto',     desc: 'LLM picks the size',    detail: 'AI picks agent & tick counts based on your scenario.' },
  { id: 'fast',     label: 'Fast',     desc: '4 agents · 8 ticks',   detail: 'Quick gut check. ~1 min.' },
  { id: 'balanced', label: 'Balanced', desc: '6 agents · 15 ticks',  detail: 'Good depth & speed. ~3 min.' },
  { id: 'deep',     label: 'Deep',     desc: '10 agents · 25 ticks', detail: 'Thorough analysis. ~8 min.' },
  { id: 'custom',   label: 'Custom',   desc: 'You choose',           detail: 'Set agent count (3–15) & ticks (5–50).' },
]

function PresetButton({ p, isActive, onClick, isLoading }) {
  const [showTip, setShowTip] = useState(false)
  const mono = { fontFamily: 'JetBrains Mono, monospace' }

  return (
    <div style={{ position: 'relative' }}
      onMouseEnter={() => setShowTip(true)}
      onMouseLeave={() => setShowTip(false)}
    >
      <button
        type="button"
        onClick={onClick}
        disabled={isLoading}
        style={{
          ...mono,
          fontSize: 10,
          padding: '3px 10px',
          borderRadius: 2,
          border: isActive ? '1px solid #F5D98A' : '1px solid #6a6a60',
          background: isActive ? 'rgba(245,217,138,0.12)' : 'transparent',
          color: isActive ? '#F5D98A' : '#FFFFFF',
          cursor: isLoading ? 'wait' : 'pointer',
          opacity: isLoading ? 0.5 : 1,
        }}
      >
        {p.label}
      </button>
      {showTip && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: 190,
          background: '#1a1a17',
          border: '1px solid #6a6a60',
          padding: '7px 9px',
          borderRadius: 3,
          zIndex: 50,
          pointerEvents: 'none',
          marginBottom: 6,
        }}>
          <div style={{ ...mono, fontSize: 10, color: '#F5D98A', marginBottom: 3 }}>{p.desc}</div>
          <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 10, color: '#FFFFFF', lineHeight: 1.45 }}>{p.detail}</div>
        </div>
      )}
    </div>
  )
}

function SettingsRow({ preset, setPreset, agentCount, setAgentCount, tickCount, setTickCount, isLoading }) {
  const mono = { fontFamily: 'JetBrains Mono, monospace' }
  const isCustom = preset === 'custom'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '6px 20px 8px',
      borderBottom: '1px solid #3a3a32',
      background: '#0f0f0d',
    }}>
      <span style={{ ...mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#FFFFFF', flexShrink: 0 }}>
        Simulation
      </span>

      {PRESETS.map(p => (
        <PresetButton
          key={p.id}
          p={p}
          isActive={preset === p.id}
          onClick={() => setPreset(p.id)}
          isLoading={isLoading}
        />
      ))}

      {isCustom && (
        <>
          <span style={{ width: 1, height: 16, background: '#6a6a60', flexShrink: 0 }} />
          <label style={{ ...mono, fontSize: 10, color: '#FFFFFF', display: 'flex', alignItems: 'center', gap: 4 }}>
            Agents
            <input
              type="number"
              min={3}
              max={15}
              value={agentCount}
              onChange={e => setAgentCount(Math.max(3, Math.min(15, parseInt(e.target.value) || 5)))}
              disabled={isLoading}
              style={{
                ...mono,
                width: 40,
                fontSize: 12,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #6a6a60',
                borderRadius: 2,
                color: '#FFFFFF',
                textAlign: 'center',
              }}
            />
          </label>
          <label style={{ ...mono, fontSize: 10, color: '#FFFFFF', display: 'flex', alignItems: 'center', gap: 4 }}>
            Ticks
            <input
              type="number"
              min={5}
              max={50}
              value={tickCount}
              onChange={e => setTickCount(Math.max(5, Math.min(50, parseInt(e.target.value) || 15)))}
              disabled={isLoading}
              style={{
                ...mono,
                width: 40,
                fontSize: 12,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #6a6a60',
                borderRadius: 2,
                color: '#FFFFFF',
                textAlign: 'center',
              }}
            />
          </label>
          <span style={{ ...mono, fontSize: 10, color: '#FFFFFF' }}>
            ~{Math.round(agentCount * tickCount * 0.4 / 60)} min est.
          </span>
        </>
      )}
    </div>
  )
}

export default function InputBar({ onOracleResult, onStreamEvent, onEnsembleResult, onBacktestResult, isLoading, setIsLoading, prefillPrompt }) {
  const [prompt, setPrompt] = useState('')
  const cancelDemoRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (prefillPrompt) setPrompt(prefillPrompt)
  }, [prefillPrompt])
  const [documentText, setDocumentText] = useState(null)
  const [documentName, setDocumentName] = useState(null)
  const [error, setError] = useState(null)

  // Simulation settings
  const [preset, setPreset] = useState('auto')
  const [agentCount, setAgentCount] = useState(6)
  const [tickCount, setTickCount] = useState(15)
  // Ensemble size — defaults to 3 (minimum viable for detecting instability)
  const [ensembleSize, setEnsembleSize] = useState(3)

  function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      setDocumentText(ev.target.result)
      setDocumentName(file.name)
    }
    reader.readAsText(file)
  }

  function clearDocument() {
    setDocumentText(null)
    setDocumentName(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function buildRequestBody() {
    const body = {
      prompt: prompt.trim(),
    }
    if (documentText) {
      body.document_text = documentText
      body.document_name = documentName
    }
    if (preset === 'custom') {
      body.agent_count = agentCount
      body.tick_count = tickCount
    } else if (preset !== 'auto') {
      body.preset = preset
    }
    // auto mode: send nothing — backend LLM decides
    return body
  }

  async function handleConsult(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/simulate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildRequestBody()),
      })
      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()
        for (const part of parts) {
          const line = part.trim()
          if (line.startsWith('data: ')) {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'error') throw new Error(event.message)
            onStreamEvent(event)
          }
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  function handleDemo(e) {
    e.preventDefault()
    if (isLoading) return
    if (cancelDemoRef.current) cancelDemoRef.current()
    setError(null)
    setIsLoading(true)
    cancelDemoRef.current = startDemoStream((event) => {
      onStreamEvent(event)
      if (event.type === 'done') {
        setIsLoading(false)
        cancelDemoRef.current = null
      }
    })
  }

  async function handleOracle(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    try {
      const body = { ...buildRequestBody(), max_runs: 5 }
      const resp = await fetch(`${API_BASE}/api/oracle/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)
      // Stream events so the Arena/Stage update during each oracle iteration.
      // Same pattern as ensemble — forward everything except `done` through
      // onStreamEvent (so the live view animates), and call onOracleResult
      // with the final OracleLoopResult so the post-run oracle view renders
      // with coherence history, amendments, etc.
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          const event = JSON.parse(line.slice(6))
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'done') {
            onOracleResult(event.data)
          } else {
            onStreamEvent(event)
          }
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleEnsemble(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    try {
      const body = { ...buildRequestBody(), ensemble_size: ensembleSize }
      const resp = await fetch(`${API_BASE}/api/ensemble/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)
      // Stream events so the Arena/Stage update during each run. We forward
      // every event except `done` through onStreamEvent (same channel as a
      // single simulate stream); the final `done` event carries the full
      // EnsembleResult which goes to onEnsembleResult so the post-run view
      // (per-run selector, robustness badges) renders.
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          const event = JSON.parse(line.slice(6))
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'done') {
            onEnsembleResult(event.data)
          } else {
            // Forward scenario/tick/etc. so the live Arena & Stage animate.
            onStreamEvent(event)
          }
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  // Backtest mode state
  const [backtestMode, setBacktestMode] = useState(false)
  const [gtAggregate, setGtAggregate] = useState(0.5)
  const [gtConfidence, setGtConfidence] = useState('moderate')
  const [gtNotes, setGtNotes] = useState('')

  async function handleBacktest(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    try {
      const body = {
        ...buildRequestBody(),
        ground_truth_outcome: {
          aggregate_stance: gtAggregate,
          confidence: gtConfidence,
          notes: gtNotes,
        },
      }
      const resp = await fetch(`${API_BASE}/api/backtest/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let lastBacktest = null
      let lastDone = null
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop()
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          const event = JSON.parse(line.slice(6))
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'backtest') {
            // Hold the calibration score — we hand it off with the run result.
            lastBacktest = event.data
            continue
          }
          if (event.type === 'done') {
            lastDone = event.data
          }
          // Forward thinking/blueprint/scenario/tick/done to the stream renderer
          // so the backtest looks and feels the same as a regular simulation.
          onStreamEvent(event)
        }
      }
      if (lastDone && lastBacktest) {
        onBacktestResult({ run: lastDone, backtest: lastBacktest })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const inputStyle = {
    background: '#0D0D0B',
    border: '1px solid #6a6a60',
    borderRadius: '4px',
    padding: '7px 11px',
    color: '#FFFFFF',
    fontFamily: 'Syne, sans-serif',
    fontSize: '13px',
  }

  return (
    <div>
      <form onSubmit={handleConsult} style={{
        padding: '12px 20px',
        borderBottom: '1px solid #3a3a32',
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
        background: '#111110',
      }}>
        <input
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="Describe a decision... e.g. Fed raises rates 50bps"
          disabled={isLoading}
          style={{ ...inputStyle, flex: 1 }}
        />
        {/* Document upload */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.csv,.json"
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          title={documentName ? `Attached: ${documentName}` : 'Attach a document to ground the simulation'}
          style={{
            background: documentName ? 'rgba(245,217,138,0.14)' : 'transparent',
            color: documentName ? 'var(--gold)' : '#FFFFFF',
            border: `1px solid ${documentName ? 'var(--gold)' : '#6a6a60'}`,
            borderRadius: '4px',
            padding: '7px 9px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: isLoading ? 0.5 : 1,
          }}
        >
          {documentName ? `📄 ${documentName.slice(0, 12)}${documentName.length > 12 ? '…' : ''}` : '📎'}
        </button>
        {documentName && (
          <button
            type="button"
            onClick={clearDocument}
            style={{
              background: 'none',
              border: 'none',
              color: '#FFFFFF',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '0 3px',
            }}
          >×</button>
        )}
        <button
          type="button"
          onClick={handleConsult}
          disabled={isLoading || !prompt.trim()}
          title="Run a single panel — agents deliberate once and return a verdict. Fast, streamed live. Best for a first look."
          style={{
            background: isLoading ? '#3a3520' : '#F5D98A',
            color: '#0D0D0B',
            border: 'none',
            borderRadius: '4px',
            padding: '7px 15px',
            fontFamily: 'Syne, sans-serif',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: (!prompt.trim() || isLoading) ? 0.6 : 1,
          }}
        >
          {isLoading ? 'Consulting...' : 'Consult the Oracle'}
        </button>
        <button
          type="button"
          onClick={handleOracle}
          disabled={isLoading || !prompt.trim()}
          title="Self-healing loop: runs the panel, critiques each agent for coherence, amends incoherent agents via the Temple of Learning, then re-runs. Up to 5 iterations. Slower but more robust."
          style={{
            background: 'transparent',
            color: isLoading ? '#6a6a60' : '#F5D98A',
            border: '1px solid #F5D98A',
            borderRadius: '4px',
            padding: '7px 15px',
            fontFamily: 'Syne, sans-serif',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: (!prompt.trim() || isLoading) ? 0.6 : 1,
          }}
        >
          {isLoading ? 'Consulting...' : 'Oracle Loop ↻ (self-heal)'}
        </button>
        <div style={{ display: 'flex', alignItems: 'stretch', border: '1px solid #8FD18F', borderRadius: 4, overflow: 'hidden' }}>
          <button
            type="button"
            onClick={handleEnsemble}
            disabled={isLoading || !prompt.trim()}
            title={`Run ${ensembleSize} parallel simulations for statistical robustness`}
            style={{
              background: 'transparent',
              color: isLoading ? '#6a6a60' : '#8FD18F',
              border: 'none',
              padding: '7px 11px 7px 15px',
              fontFamily: 'Syne, sans-serif',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isLoading ? 'wait' : 'pointer',
              whiteSpace: 'nowrap',
              opacity: (!prompt.trim() || isLoading) ? 0.6 : 1,
            }}
          >
            {isLoading ? 'Running...' : 'Ensemble ×'}
          </button>
          <select
            value={ensembleSize}
            onChange={e => setEnsembleSize(parseInt(e.target.value) || 3)}
            disabled={isLoading}
            title="How many parallel runs (1–5). More runs = more robust but linearly slower."
            style={{
              background: 'transparent',
              color: isLoading ? '#6a6a60' : '#8FD18F',
              border: 'none',
              borderLeft: '1px solid rgba(143,209,143,0.5)',
              padding: '0 9px',
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isLoading ? 'wait' : 'pointer',
              outline: 'none',
              appearance: 'none',
            }}
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
            <option value={5}>5</option>
          </select>
        </div>
        <button
          type="button"
          onClick={() => setBacktestMode(m => !m)}
          disabled={isLoading}
          title={backtestMode ? 'Hide backtest mode' : 'Backtest against a known outcome'}
          style={{
            background: backtestMode ? 'rgba(224,157,138,0.14)' : 'transparent',
            color: backtestMode ? '#E09D8A' : '#FFFFFF',
            border: `1px solid ${backtestMode ? '#E09D8A' : '#6a6a60'}`,
            borderRadius: '4px',
            padding: '7px 11px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: isLoading ? 0.5 : 1,
          }}
        >
          {backtestMode ? '✓ Backtest' : '⏱ Backtest'}
        </button>
        <button
          type="button"
          onClick={handleDemo}
          disabled={isLoading}
          title="Run a mock demo — no API key needed"
          style={{
            background: 'transparent',
            color: isLoading ? '#6a6a60' : '#FFFFFF',
            border: '1px solid #6a6a60',
            borderRadius: '4px',
            padding: '7px 11px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            letterSpacing: '0.08em',
            opacity: isLoading ? 0.5 : 1,
          }}
        >
          ▶ demo
        </button>
        {error && (
          <span style={{ color: '#E09D8A', fontSize: '11px', fontFamily: 'JetBrains Mono, monospace' }}>
            {error}
          </span>
        )}
      </form>
      <SettingsRow
        preset={preset}
        setPreset={setPreset}
        agentCount={agentCount}
        setAgentCount={setAgentCount}
        tickCount={tickCount}
        setTickCount={setTickCount}
        isLoading={isLoading}
      />
      {backtestMode && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '6px 20px 8px',
          borderBottom: '1px solid #3a3a32',
          background: '#0f0f0d',
        }}>
          <span style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: '#E09D8A',
            flexShrink: 0,
          }}>
            Ground Truth
          </span>
          <label style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            Actual stance
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={gtAggregate}
              onChange={e => setGtAggregate(Math.max(0, Math.min(1, parseFloat(e.target.value) || 0.5)))}
              disabled={isLoading}
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                width: 50,
                fontSize: 12,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #6a6a60',
                borderRadius: 2,
                color: '#FFFFFF',
                textAlign: 'center',
              }}
            />
          </label>
          <label style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            Confidence
            <select
              value={gtConfidence}
              onChange={e => setGtConfidence(e.target.value)}
              disabled={isLoading}
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #6a6a60',
                borderRadius: 2,
                color: '#FFFFFF',
              }}
            >
              <option value="high">High</option>
              <option value="moderate">Moderate</option>
              <option value="low">Low</option>
              <option value="polarized">Polarized</option>
            </select>
          </label>
          <input
            type="text"
            value={gtNotes}
            onChange={e => setGtNotes(e.target.value)}
            placeholder="What actually happened..."
            disabled={isLoading}
            style={{
              flex: 1,
              fontFamily: 'Syne, sans-serif',
              fontSize: 12,
              padding: '4px 8px',
              background: '#0D0D0B',
              border: '1px solid #6a6a60',
              borderRadius: 2,
              color: '#FFFFFF',
            }}
          />
          <button
            type="button"
            onClick={handleBacktest}
            disabled={isLoading || !prompt.trim()}
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 11,
              padding: '4px 12px',
              borderRadius: 2,
              border: '1px solid #E09D8A',
              background: 'rgba(224,157,138,0.14)',
              color: '#E09D8A',
              cursor: isLoading ? 'wait' : 'pointer',
              opacity: (!prompt.trim() || isLoading) ? 0.5 : 1,
            }}
          >
            Run Backtest
          </button>
        </div>
      )}
    </div>
  )
}
