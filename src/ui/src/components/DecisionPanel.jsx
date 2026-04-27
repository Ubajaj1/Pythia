import { useState } from 'react'

const confidenceColors = {
  high: '#6A9B6A',
  moderate: '#A88C52',
  low: '#9B6A6A',
  polarized: '#C08878',
}

function ArgumentCard({ arg, direction }) {
  const arrow = direction === 'for' ? '↑' : '↓'
  const color = direction === 'for' ? '#6A9B6A' : '#9B6A6A'

  return (
    <div style={{
      padding: '8px 10px',
      borderLeft: `2px solid ${color}`,
      marginBottom: 6,
    }}>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 600,
        fontSize: 10,
        color: 'var(--text-primary)',
      }}>
        {arrow} {arg.agent_name}
        <span style={{
          fontWeight: 300,
          color: 'var(--text-muted)',
          marginLeft: 6,
          fontSize: 9,
        }}>{arg.agent_role}</span>
      </div>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 300,
        fontSize: 10,
        color: 'var(--text-ui)',
        marginTop: 3,
        lineHeight: 1.5,
      }}>{arg.reasoning}</div>
    </div>
  )
}

export default function DecisionPanel({ decisionSummary, stanceSpectrum }) {
  const [expanded, setExpanded] = useState(false)

  if (!decisionSummary) return null

  const ds = decisionSummary
  const confColor = confidenceColors[ds.confidence] || confidenceColors.low
  const lowLabel = stanceSpectrum?.[0] || '0.0'
  const highLabel = stanceSpectrum?.[4] || '1.0'

  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      background: 'var(--surface-warm)',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      {/* Collapsed summary bar — always visible */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '10px 28px',
          cursor: 'pointer',
          gap: 16,
          userSelect: 'none',
        }}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 8,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--gold-ui)',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>
          // Oracle Verdict
        </div>

        <div style={{
          flex: 1,
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 12,
          color: 'var(--text-primary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {ds.verdict}
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexShrink: 0,
        }}>
          {/* Confidence badge */}
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: confColor,
            border: `1px solid ${confColor}`,
            padding: '2px 8px',
            borderRadius: 2,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}>
            {ds.confidence}
          </div>

          {/* Stance indicator */}
          <div style={{
            width: 80,
            position: 'relative',
          }}>
            <div style={{
              height: 3,
              background: 'var(--text-dim)',
              borderRadius: 2,
            }} />
            <div style={{
              position: 'absolute',
              top: -3,
              left: `${ds.verdict_stance * 100}%`,
              width: 9,
              height: 9,
              borderRadius: '50%',
              background: 'var(--gold)',
              transform: 'translateX(-50%)',
              boxShadow: '0 0 6px rgba(168,140,82,0.4)',
            }} />
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

          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 0.3s ease',
          }}>▾</div>
        </div>
      </div>

      {/* Expanded detail */}
      <div style={{
        maxHeight: expanded ? 400 : 0,
        overflow: 'hidden',
        transition: 'max-height 0.4s ease',
      }}>
        <div style={{
          padding: '0 28px 16px',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px 24px',
        }}>
          {/* Arguments For */}
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 8,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#6A9B6A',
              marginBottom: 8,
            }}>Arguments For</div>
            {ds.arguments_for?.map((arg, i) => (
              <ArgumentCard key={i} arg={arg} direction="for" />
            ))}
            {(!ds.arguments_for || ds.arguments_for.length === 0) && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                No strong arguments recorded
              </div>
            )}
          </div>

          {/* Arguments Against */}
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 8,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#9B6A6A',
              marginBottom: 8,
            }}>Arguments Against</div>
            {ds.arguments_against?.map((arg, i) => (
              <ArgumentCard key={i} arg={arg} direction="against" />
            ))}
            {(!ds.arguments_against || ds.arguments_against.length === 0) && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
                No strong arguments recorded
              </div>
            )}
          </div>

          {/* Key Risk */}
          {ds.key_risk && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#C08878',
                marginBottom: 4,
              }}>Key Risk</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 300,
                fontSize: 10,
                color: 'var(--text-ui)',
                lineHeight: 1.6,
              }}>{ds.key_risk}</div>
            </div>
          )}

          {/* Influence Narrative */}
          {ds.influence_narrative && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--gold-ui)',
                marginBottom: 4,
              }}>How Agents Influenced Each Other</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 300,
                fontSize: 10,
                color: 'var(--text-ui)',
                lineHeight: 1.6,
              }}>{ds.influence_narrative}</div>
            </div>
          )}

          {/* What Could Change */}
          {ds.what_could_change && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--text-ui)',
                marginBottom: 4,
              }}>What Could Change the Outcome</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 300,
                fontSize: 10,
                color: 'var(--text-ui)',
                lineHeight: 1.6,
              }}>{ds.what_could_change}</div>
            </div>
          )}

          {/* Actionable Takeaways */}
          {ds.actionable_takeaways?.length > 0 && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--gold)',
                marginBottom: 6,
              }}>Before You Decide — Do This</div>
              {ds.actionable_takeaways.map((t, i) => (
                <div key={i} style={{
                  display: 'flex',
                  gap: 8,
                  padding: '4px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.02)',
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    color: 'var(--gold)',
                    flexShrink: 0,
                  }}>{i + 1}.</span>
                  <span style={{
                    fontFamily: 'var(--font-ui)',
                    fontWeight: 400,
                    fontSize: 10,
                    color: 'var(--text-primary)',
                    lineHeight: 1.6,
                  }}>{t}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
