import { useState } from 'react'

function StanceBar({ value, spectrum }) {
  const lowLabel = spectrum?.[0] || '0.0'
  const highLabel = spectrum?.[4] || '1.0'

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{
        height: 4,
        background: '#6a6a60',
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
          boxShadow: '0 0 5px rgba(245,217,138,0.5)',
        }} />
      </div>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: 4,
      }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#FFFFFF' }}>
          {lowLabel}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#FFFFFF' }}>
          {highLabel}
        </span>
      </div>
    </div>
  )
}

function InfluenceItem({ edge, agentNames }) {
  const isHerd = edge.edge_type === 'herd_pressure' || edge.source_id === '__aggregate__'
  const sourceName = isHerd ? 'crowd aggregate' : (agentNames[edge.source_id] || edge.source_id)
  const delta = edge.influence_delta
  const color = delta > 0 ? '#8FD18F' : delta < 0 ? '#E09A9A' : '#FFFFFF'

  return (
    <div style={{
      padding: '5px 0',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
    }}>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: '#FFFFFF',
      }}>
        tick {edge.tick} · {isHerd ? '◉ herd pressure' : `← ${sourceName}`}
      </div>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 400,
        fontSize: 11,
        color: '#FFFFFF',
        marginTop: 2,
      }}>
        {edge.message?.slice(0, 80)}{edge.message?.length > 80 ? '…' : ''}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: '#FFFFFF',
        marginTop: 2,
      }}>
        target stance: {edge.target_stance_before?.toFixed(2) ?? '—'} → {edge.target_stance_after?.toFixed(2) ?? '—'}
        {' '}
        <span style={{ color }}>
          ({delta > 0 ? '+' : ''}{delta.toFixed(2)} this tick)
        </span>
      </div>
    </div>
  )
}

export default function AgentDetail({ agent, agentInfo, influences, trajectory, spectrum, onClose, agentNames }) {
  if (!agent) return null

  const [tab, setTab] = useState('info')

  // Default to a lookup that just returns the agent's own name
  const names = agentNames || {}

  const tabStyle = (active) => ({
    fontFamily: 'var(--font-mono)',
    fontSize: 9,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: active ? 'var(--gold)' : '#FFFFFF',
    background: 'none',
    border: 'none',
    borderBottom: active ? '2px solid var(--gold)' : '2px solid transparent',
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
        padding: '13px 14px 9px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
      }}>
        <div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 600,
            fontSize: 13,
            color: '#FFFFFF',
          }}>{agent.name}</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 400,
            fontSize: 10,
            color: 'var(--gold)',
            marginTop: 2,
          }}>{agentInfo?.role || agent.trait}</div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#FFFFFF',
            cursor: 'pointer',
            fontFamily: 'var(--font-mono)',
            fontSize: 15,
            lineHeight: 1,
            padding: '0 5px',
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
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#FFFFFF',
                  marginBottom: 4,
                }}>Persona</div>
                <div style={{
                  fontFamily: 'var(--font-ui)',
                  fontWeight: 400,
                  fontSize: 12,
                  color: '#FFFFFF',
                  lineHeight: 1.6,
                }}>{agentInfo.persona}</div>
              </div>
            )}

            {/* Bias */}
            <div style={{ marginBottom: 12 }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#FFFFFF',
                marginBottom: 4,
              }}>Cognitive Bias</div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                color: 'var(--gold)',
              }}>{agentInfo?.bias || agent.trait}</div>
            </div>

            {/* Current Stance */}
            <div style={{ marginBottom: 12 }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#FFFFFF',
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
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#FFFFFF',
                  marginBottom: 6,
                }}>Stance Over Time</div>
                <svg viewBox={`0 0 ${sparkW} ${sparkH}`} style={{ width: '100%', height: 28 }}>
                  <polyline
                    points={sparkPoints}
                    fill="none"
                    stroke="var(--gold)"
                    strokeWidth="1.3"
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
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#FFFFFF',
                  marginBottom: 4,
                }}>Latest Reasoning</div>
                <div style={{
                  fontFamily: 'var(--font-display)',
                  fontStyle: 'italic',
                  fontSize: 12,
                  color: '#FFFFFF',
                  lineHeight: 1.6,
                }}>"{trajectory[trajectory.length - 1].reasoning}"</div>
              </div>
            )}
          </>
        )}

        {tab === 'influence' && (
          <>
            {influences && influences.length > 0 ? (
              <>
                {/* Summary — cumulative net shift across all recorded influences */}
                {(() => {
                  const netShift = influences.reduce((s, e) => s + (e.influence_delta || 0), 0)
                  const netColor = netShift > 0 ? '#8FD18F' : netShift < 0 ? '#E09A9A' : '#FFFFFF'
                  return (
                    <div style={{
                      padding: '8px 10px',
                      marginBottom: 10,
                      background: 'rgba(245,217,138,0.06)',
                      border: '1px solid #6a6a60',
                      borderRadius: 3,
                    }}>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                        color: '#FFFFFF',
                        marginBottom: 4,
                      }}>
                        {influences.length} influence{influences.length === 1 ? '' : 's'} recorded
                      </div>
                      <div style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12,
                        color: netColor,
                      }}>
                        Net tick-shift contribution: {netShift > 0 ? '+' : ''}{netShift.toFixed(2)}
                      </div>
                      <div style={{
                        fontFamily: 'var(--font-ui)',
                        fontStyle: 'italic',
                        fontSize: 10,
                        color: '#FFFFFF',
                        marginTop: 4,
                        lineHeight: 1.5,
                        opacity: 0.85,
                      }}>
                        Each entry shows the stance change during the tick the message arrived. Bias mechanics and herd pressure also contribute.
                      </div>
                    </div>
                  )
                })()}
                {influences.map((edge, i) => (
                  <InfluenceItem
                    key={i}
                    edge={edge}
                    agentNames={names}
                  />
                ))}
              </>
            ) : (
              <div style={{
                fontFamily: 'var(--font-display)',
                fontStyle: 'italic',
                fontSize: 12,
                color: '#FFFFFF',
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
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 10,
                      color: '#FFFFFF',
                    }}>tick {node.tick}</span>
                    <span style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 11,
                      color: 'var(--gold)',
                    }}>{node.stance.toFixed(2)}</span>
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-ui)',
                    fontWeight: 400,
                    fontSize: 11,
                    color: '#FFFFFF',
                    marginTop: 2,
                  }}>
                    {node.action} · {node.emotion}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-display)',
                    fontStyle: 'italic',
                    fontSize: 11,
                    color: '#FFFFFF',
                    marginTop: 2,
                    opacity: 0.9,
                  }}>"{node.reasoning}"</div>
                </div>
              ))
            ) : (
              <div style={{
                fontFamily: 'var(--font-display)',
                fontStyle: 'italic',
                fontSize: 12,
                color: '#FFFFFF',
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
