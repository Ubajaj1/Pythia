import { useState, useEffect, useRef } from 'react'
import { startDemoStream } from '../simulation/demo'

const API_BASE = ''

export default function InputBar({ onOracleResult, onStreamEvent, isLoading, setIsLoading, prefillPrompt }) {
  const [prompt, setPrompt] = useState('')
  const cancelDemoRef = useRef(null)

  useEffect(() => {
    if (prefillPrompt) setPrompt(prefillPrompt)
  }, [prefillPrompt])
  const [context, setContext] = useState('')
  const [error, setError] = useState(null)

  async function handleConsult(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/simulate/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), context: context.trim() || undefined }),
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
      const resp = await fetch(`${API_BASE}/api/oracle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim(), context: context.trim() || undefined, max_runs: 5 }),
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
  )
}
