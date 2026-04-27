import { useState } from 'react'

function StanceBar({ value, spectrum }) {
  const lowLabel = spectrum?.[0] || '0.0'
  const highLabel = spectrum?.[4] || '1.0'

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{
        height: 4,
        background: 'var(--text-dim)',
        borderRadius: 2,
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute',
          top: -2,
          left: `${value * 100}%`,
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: 'var(--gold)',
          transform: 'translateX(-50%)',
          boxShadow: '0 0 4px rgba(168,140,82,0.3)',
        }} />
      </div>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 4,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7, color: 'var(--text-muted)' }}>
          {lowLabel}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7, color: 'var(--text-muted)' }}>
          {highLabel}
        </span>
      </div>
    </div>
  )
}

function InfluenceItem({ edge, agentNames }) {
  const sourceName = agentNames[edge.source_id] || edge.source_id
  const delta = edge.influence_delta
  const color = delta > 0 ? '#6A9B6A' : delta < 0 ? '#9B6A6A' : 'var(--text-muted)'

  return (
    <div style={{
      padding: '4px 0',
      borderBottom: '1px solid rgba(255,255,255,0.02)',
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        color: 'var(--text-muted)',
      }}>
        tick {edge.tick} · {edge.edge_type === 'herd_pressure' ? '◉ herd' : `← ${sourceName}`}
      </div>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 300,
        fontSize: 9,
        color: 'var(--text-ui)',
        marginTop: 2,
      }}>
        {edge.message?.slice(0, 80)}{edge.message?.length > 80 ? '…' : ''}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        color,
        marginTop: 2,
      }}>
        {delta > 0 ? '+' : ''}{delta.toFixed(2)} stance shift
      </div>
    </div>
  )
}

export default function AgentDetail({ agent, agentInfo, influences, trajectory, spectrum, onClose }) {
  if (!agent) return null

  const [tab, setTab] = useState('info')

  const tabStyle = (active) => ({
    fontFamily: 'var(--font-mono)',
    fontSize: 8,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: active ? 'var(--gold)' : 'var(--text-muted)',
    background: 'none',
    border: 'none',
    borderBottom: active ? '1px solid var(--gold)' : '1px solid transparent',
    padding: '4px 8px',
    cursor: 'pointer',
  })

  // Build sparkline from trajectory
  const stances = trajectory?.map(n => n.stance) || []
  const sparkW = 140
  const sparkH = 24
  const sparkPoints = stances.map((s, i) => {
    const x = (i / Math.max(stances.length - 1, 1)) * sparkW
    const y = sparkH - s * sparkH
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 210,
      width: 260,
      height: '100%',
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      zIndex: 20,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 14px 10px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 600,
            fontSize: 12,
            color: 'var(--text-primary)',
          }}>{agent.name}</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 300,
            fontSize: 9,
            color: 'var(--gold)',
            marginTop: 2,
          }}>{agentInfo?.role || agent.trait}</div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontSize: 14,
            lineHeight: 1,
            padding: '0 4px',
          }}
        >×</button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: 4,
        padding: '8px 14px 0',
        borderBottom: '1px solid var(--border)',
      }}>
        <button style={tabStyle(tab === 'info')} onClick={() => setTab('info')}>Profile</button>
        <button style={tabStyle(tab === 'influence')} onClick={() => setTab('influence')}>Influences</button>
        <button style={tabStyle(tab === 'trajectory')} onClick={() => setTab('trajectory')}>Trajectory</button>
      </div>

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 14px',
      }}>
        {tab === 'info' && (
          <>
            {/* Persona */}
            {agentInfo?.persona && (
              <div style={{ marginBottom: 12 }}>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 8,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: 4,
                }}>Persona</div>
                <div style={{
                  fontFamily: 'var(--font-ui)',
                  fontWeight: 300,
                  fontSize: 10,
                  color: 'var(--text-ui)',
                  lineHeight: 1.6,
                }}>{agentInfo.persona}</div>
              </div>
            )}

            {/* Bias */}
            <div style={{ marginBottom: 12 }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                marginBottom: 4,
              }}>Cognitive Bias</div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--gold)',
              }}>{agentInfo?.bias || agent.trait}</div>
            </div>

            {/* Current Stance */}
            <div style={{ marginBottom: 12 }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                marginBottom: 4,
              }}>Current Stance</div>
              <StanceBar
                value={stances.length > 0 ? stances[stances.length - 1] : (agentInfo?.initial_stance || 0.5)}
                spectrum={spectrum}
              />
            </div>

            {/* Sparkline */}
            {stances.length > 1 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 8,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: 6,
                }}>Stance Over Time</div>
                <svg viewBox={`0 0 ${sparkW} ${sparkH}`} style={{ width: '100%', height: 28 }}>
                  <polyline
                    points={sparkPoints}
                    fill="none"
                    stroke="var(--gold)"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                  />
                </svg>
              </div>
            )}

            {/* Latest Reasoning */}
            {trajectory && trajectory.length > 0 && (
              <div>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 8,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: 4,
                }}>Latest Reasoning</div>
                <div style={{
                  fontFamily: 'var(--font-display)',
                  fontStyle: 'italic',
                  fontSize: 10,
                  color: 'var(--text-ui)',
                  lineHeight: 1.6,
                }}>"{trajectory[trajectory.length - 1].reasoning}"</div>
              </div>
            )}
          </>
        )}

        {tab === 'influence' && (
          <>
            {influences && influences.length > 0 ? (
              influences.map((edge, i) => (
                <InfluenceItem
                  key={i}
                  edge={edge}
                  agentNames={
                    Object.fromEntries(
                      (trajectory || []).map(n => [n.agent_id, agent.name])
                    )
                  }
                />
              ))
            ) : (
              <div style={{
                fontFamily: 'var(--font-display)',
                fontStyle: 'italic',
                fontSize: 10,
                color: 'var(--text-muted)',
                textAlign: 'center',
                marginTop: 20,
              }}>No influence events recorded</div>
            )}
          </>
        )}

        {tab === 'trajectory' && (
          <>
            {trajectory && trajectory.length > 0 ? (
              trajectory.map((node, i) => (
                <div key={i} style={{
                  padding: '6px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 8,
                      color: 'var(--text-muted)',
                    }}>tick {node.tick}</span>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 9,
                      color: 'var(--gold)',
                    }}>{node.stance.toFixed(2)}</span>
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-ui)',
                    fontWeight: 300,
                    fontSize: 9,
                    color: 'var(--text-ui)',
                    marginTop: 2,
                  }}>
                    {node.action} · {node.emotion}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-display)',
                    fontStyle: 'italic',
                    fontSize: 9,
                    color: 'var(--text-muted)',
                    marginTop: 2,
                  }}>"{node.reasoning}"</div>
                </div>
              ))
            ) : (
              <div style={{
                fontFamily: 'var(--font-display)',
                fontStyle: 'italic',
                fontSize: 10,
                color: 'var(--text-muted)',
                textAlign: 'center',
                marginTop: 20,
              }}>Simulation in progress…</div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
