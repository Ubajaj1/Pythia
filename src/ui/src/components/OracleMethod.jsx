import { useState } from 'react'

/**
 * The Oracle's Method — transparency panel showing how the simulation was computed.
 *
 * Shows: agent count, tick count, agents per role, biases assigned, confidence
 * thresholds, ensemble size, seed, and LLM provider/model.
 *
 * Designed as a collapsible drawer that sits above the DecisionPanel footer.
 */
export default function OracleMethod({ methodology, runId }) {
  const [open, setOpen] = useState(false)

  if (!methodology) return null

  const m = methodology
  const mono = { fontFamily: 'var(--font-mono)', fontSize: 10 }
  const label = { ...mono, fontSize: 9, letterSpacing: '0.10em', textTransform: 'uppercase', color: '#FFFFFF', marginBottom: 4 }
  const value = { ...mono, color: '#FFFFFF' }

  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      background: '#0f0f0d',
      flexShrink: 0,
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '7px 28px',
          cursor: 'pointer',
          gap: 12,
          userSelect: 'none',
        }}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color: 'var(--gold)',
        }}>
          ◈ The Oracle's Method
        </div>
        <div style={{
          flex: 1,
          height: 1,
          background: '#3a3a32',
        }} />
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: '#FFFFFF',
          transform: open ? 'rotate(180deg)' : 'rotate(0)',
          transition: 'transform 0.3s ease',
        }}>▾</div>
      </div>

      <div style={{
        maxHeight: open ? 320 : 0,
        overflow: 'hidden',
        transition: 'max-height 0.4s ease',
      }}>
        <div style={{
          padding: '4px 28px 14px',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '10px 20px',
        }}>
          {/* Panel composition */}
          <div>
            <div style={label}>Panel</div>
            <div style={value}>
              {m.agent_count} agents · {m.tick_count} ticks
            </div>
          </div>

          {/* Ensemble */}
          <div>
            <div style={label}>Ensemble</div>
            <div style={value}>
              {m.ensemble_size > 1 ? `${m.ensemble_size} runs` : 'Single run'}
            </div>
          </div>

          {/* LLM */}
          <div>
            <div style={label}>Model</div>
            <div style={value}>
              {m.llm_model}
            </div>
          </div>

          {/* Seed */}
          <div>
            <div style={label}>Seed</div>
            <div style={value}>
              {m.seed != null ? m.seed : 'none (non-deterministic)'}
            </div>
          </div>

          {/* Roles */}
          {m.agents_per_role && Object.keys(m.agents_per_role).length > 0 && (
            <div style={{ gridColumn: '1 / 3' }}>
              <div style={label}>Roles</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(m.agents_per_role).map(([role, count]) => (
                  <span key={role} style={{
                    ...mono,
                    color: '#FFFFFF',
                    background: '#1f1f1b',
                    padding: '2px 8px',
                    borderRadius: 2,
                  }}>
                    {role} ×{count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Biases */}
          {m.biases_assigned && Object.keys(m.biases_assigned).length > 0 && (
            <div style={{ gridColumn: '3 / 5' }}>
              <div style={label}>Biases</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {[...new Set(Object.values(m.biases_assigned))].map(bias => {
                  const count = Object.values(m.biases_assigned).filter(b => b === bias).length
                  return (
                    <span key={bias} style={{
                      ...mono,
                      color: 'var(--gold)',
                      background: 'rgba(245,217,138,0.12)',
                      padding: '2px 8px',
                      borderRadius: 2,
                    }}>
                      {bias}{count > 1 ? ` ×${count}` : ''}
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          {/* Confidence thresholds */}
          {m.confidence_thresholds && Object.keys(m.confidence_thresholds).length > 0 && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={label}>Confidence Thresholds</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                {Object.entries(m.confidence_thresholds).map(([key, val]) => (
                  <span key={key} style={{
                    ...mono,
                    color: '#FFFFFF',
                  }}>
                    {key.replace(/_/g, ' ')}: {val}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Run ID */}
          {runId && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{ ...mono, color: '#FFFFFF', opacity: 0.6 }}>
                run: {runId}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
