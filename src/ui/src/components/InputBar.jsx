import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function InputBar({ onSimulationResult, onOracleResult, isLoading, setIsLoading }) {
  const [prompt, setPrompt] = useState('')
  const [context, setContext] = useState('')
  const [error, setError] = useState(null)

  async function handleSubmit(e, mode) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    const endpoint = mode === 'oracle' ? '/api/oracle' : '/api/simulate'
    const body = mode === 'oracle'
      ? { prompt: prompt.trim(), context: context.trim() || undefined, max_runs: 5 }
      : { prompt: prompt.trim(), context: context.trim() || undefined }

    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!resp.ok) throw new Error(`Request failed: ${resp.status}`)

      const result = await resp.json()
      if (mode === 'oracle') {
        onOracleResult(result)
      } else {
        onSimulationResult(result)
      }
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
    <form style={{
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
        onClick={e => handleSubmit(e, 'simulate')}
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
        onClick={e => handleSubmit(e, 'oracle')}
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
      {error && (
        <span style={{ color: '#C08878', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </span>
      )}
    </form>
  )
}
