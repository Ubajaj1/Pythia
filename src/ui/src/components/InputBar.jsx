import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

export default function InputBar({ onSimulationResult, isLoading, setIsLoading }) {
  const [prompt, setPrompt] = useState('')
  const [context, setContext] = useState('')
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!prompt.trim() || isLoading) return

    setIsLoading(true)
    setError(null)

    try {
      const resp = await fetch(`${API_BASE}/api/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          context: context.trim() || undefined,
        }),
      })

      if (!resp.ok) {
        throw new Error(`Simulation failed: ${resp.status}`)
      }

      const result = await resp.json()
      onSimulationResult(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{
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
        style={{
          flex: 1,
          background: '#0D0D0B',
          border: '1px solid #2a2a25',
          borderRadius: '4px',
          padding: '8px 12px',
          color: '#d4c9a8',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
        }}
      />
      <input
        type="text"
        value={context}
        onChange={e => setContext(e.target.value)}
        placeholder="Optional context..."
        disabled={isLoading}
        style={{
          width: '200px',
          background: '#0D0D0B',
          border: '1px solid #2a2a25',
          borderRadius: '4px',
          padding: '8px 12px',
          color: '#d4c9a8',
          fontFamily: 'Syne, sans-serif',
          fontSize: '13px',
        }}
      />
      <button
        type="submit"
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
      {error && (
        <span style={{ color: '#C08878', fontSize: '12px', fontFamily: 'JetBrains Mono, monospace' }}>
          {error}
        </span>
      )}
    </form>
  )
}
