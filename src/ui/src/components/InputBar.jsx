import { useState, useEffect, useRef } from 'react'
import { startDemoStream } from '../simulation/demo'

const API_BASE = ''

const PRESETS = [
  { id: 'auto',     label: 'Auto',     desc: 'LLM picks based on scenario complexity' },
  { id: 'fast',     label: 'Fast',     desc: '4 agents · 8 ticks · ~1 min' },
  { id: 'balanced', label: 'Balanced', desc: '6 agents · 15 ticks · ~3 min' },
  { id: 'deep',     label: 'Deep',     desc: '10 agents · 25 ticks · ~8 min' },
  { id: 'custom',   label: 'Custom',   desc: 'You choose' },
]

function SettingsRow({ preset, setPreset, agentCount, setAgentCount, tickCount, setTickCount, isLoading }) {
  const mono = { fontFamily: 'JetBrains Mono, monospace' }
  const isCustom = preset === 'custom'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      padding: '6px 20px 8px',
      borderBottom: '1px solid #1a1a17',
      background: '#0f0f0d',
    }}>
      <span style={{ ...mono, fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#3a3a35', flexShrink: 0 }}>
        Simulation
      </span>

      {PRESETS.map(p => (
        <button
          key={p.id}
          type="button"
          onClick={() => setPreset(p.id)}
          disabled={isLoading}
          title={p.desc}
          style={{
            ...mono,
            fontSize: 9,
            padding: '3px 10px',
            borderRadius: 2,
            border: preset === p.id ? '1px solid #A88C52' : '1px solid #2a2a25',
            background: preset === p.id ? 'rgba(168,140,82,0.1)' : 'transparent',
            color: preset === p.id ? '#A88C52' : '#4a4a44',
            cursor: isLoading ? 'wait' : 'pointer',
            opacity: isLoading ? 0.4 : 1,
          }}
        >
          {p.label}
        </button>
      ))}

      {isCustom && (
        <>
          <span style={{ width: 1, height: 16, background: '#2a2a25', flexShrink: 0 }} />
          <label style={{ ...mono, fontSize: 8, color: '#4a4a44', display: 'flex', alignItems: 'center', gap: 4 }}>
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
                width: 38,
                fontSize: 10,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #2a2a25',
                borderRadius: 2,
                color: '#d4c9a8',
                textAlign: 'center',
              }}
            />
          </label>
          <label style={{ ...mono, fontSize: 8, color: '#4a4a44', display: 'flex', alignItems: 'center', gap: 4 }}>
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
                width: 38,
                fontSize: 10,
                padding: '2px 4px',
                background: '#0D0D0B',
                border: '1px solid #2a2a25',
                borderRadius: 2,
                color: '#d4c9a8',
                textAlign: 'center',
              }}
            />
          </label>
          <span style={{ ...mono, fontSize: 7, color: '#2a2a25' }}>
            ~{Math.round(agentCount * tickCount * 0.4 / 60)} min est.
          </span>
        </>
      )}
    </div>
  )
}

export default function InputBar({ onOracleResult, onStreamEvent, isLoading, setIsLoading, prefillPrompt }) {
  const [prompt, setPrompt] = useState('')
  const cancelDemoRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (prefillPrompt) setPrompt(prefillPrompt)
  }, [prefillPrompt])
  const [context, setContext] = useState('')
  const [documentText, setDocumentText] = useState(null)
  const [documentName, setDocumentName] = useState(null)
  const [error, setError] = useState(null)

  // Simulation settings
  const [preset, setPreset] = useState('auto')
  const [agentCount, setAgentCount] = useState(6)
  const [tickCount, setTickCount] = useState(15)

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
      context: context.trim() || undefined,
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
      const resp = await fetch(`${API_BASE}/api/oracle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)
      const result = await resp.json()
      onOracleResult(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const inputStyle = {
    background: '#0D0D0B',
    border: '1px solid #2a2a25',
    borderRadius: '4px',
    padding: '8px 12px',
    color: '#d4c9a8',
    fontFamily: 'Syne, sans-serif',
    fontSize: '13px',
  }

  return (
    <div>
      <form onSubmit={handleConsult} style={{
        padding: '12px 20px',
        borderBottom: '1px solid #1a1a17',
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
        <input
          type="text"
          value={context}
          onChange={e => setContext(e.target.value)}
          placeholder="Optional context..."
          disabled={isLoading}
          style={{ ...inputStyle, width: '200px' }}
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
            background: documentName ? 'rgba(168,140,82,0.12)' : 'transparent',
            color: documentName ? 'var(--gold)' : '#4a4a44',
            border: `1px solid ${documentName ? 'var(--gold-dim)' : '#2a2a25'}`,
            borderRadius: '4px',
            padding: '8px 10px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: isLoading ? 0.4 : 1,
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
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '0 2px',
            }}
          >×</button>
        )}
        <button
          type="button"
          onClick={handleConsult}
          disabled={isLoading || !prompt.trim()}
          style={{
            background: isLoading ? '#3a3520' : '#A88C52',
            color: '#0D0D0B',
            border: 'none',
            borderRadius: '4px',
            padding: '8px 16px',
            fontFamily: 'Syne, sans-serif',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: (!prompt.trim() || isLoading) ? 0.5 : 1,
          }}
        >
          {isLoading ? 'Consulting...' : 'Consult the Oracle'}
        </button>
        <button
          type="button"
          onClick={handleOracle}
          disabled={isLoading || !prompt.trim()}
          style={{
            background: 'transparent',
            color: isLoading ? '#3a3520' : '#A88C52',
            border: '1px solid #A88C52',
            borderRadius: '4px',
            padding: '8px 16px',
            fontFamily: 'Syne, sans-serif',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            opacity: (!prompt.trim() || isLoading) ? 0.5 : 1,
          }}
        >
          {isLoading ? 'Consulting...' : 'Oracle Loop ↻'}
        </button>
        <button
          type="button"
          onClick={handleDemo}
          disabled={isLoading}
          title="Run a mock demo — no API key needed"
          style={{
            background: 'transparent',
            color: isLoading ? '#2a2a25' : '#4a4a44',
            border: '1px solid #2a2a25',
            borderRadius: '4px',
            padding: '8px 12px',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '11px',
            cursor: isLoading ? 'wait' : 'pointer',
            whiteSpace: 'nowrap',
            letterSpacing: '0.08em',
            opacity: isLoading ? 0.4 : 1,
          }}
        >
          ▶ demo
        </button>
        {error && (
          <span style={{ color: '#C08878', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
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
    </div>
  )
}
