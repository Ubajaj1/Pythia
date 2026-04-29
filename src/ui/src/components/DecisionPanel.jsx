import { useState, useEffect } from 'react'

const confidenceColors = {
  high: '#6A9B6A',
  moderate: '#A88C52',
  low: '#9B6A6A',
  polarized: '#C08878',
}

function ArgumentCard({ arg, direction }) {
  const arrow = direction === 'for' ? '↑' : '↓'
  const color = direction === 'for' ? '#8FD18F' : '#E09A9A'

  return (
    <div style={{
      padding: '7px 9px',
      borderLeft: `2px solid ${color}`,
      marginBottom: 5,
    }}>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 600,
        fontSize: 11,
        color: '#FFFFFF',
      }}>
        {arrow} {arg.agent_name}
        <span style={{
          fontWeight: 400,
          color: '#FFFFFF',
          marginLeft: 6,
          fontSize: 10,
          opacity: 0.85,
        }}>{arg.agent_role}</span>
      </div>
      <div style={{
        fontFamily: 'var(--font-ui)',
        fontWeight: 400,
        fontSize: 11,
        color: '#FFFFFF',
        marginTop: 3,
        lineHeight: 1.55,
      }}>{arg.reasoning}</div>
    </div>
  )
}

export default function DecisionPanel({ decisionSummary, stanceSpectrum, ensembleResult, backtestResult }) {
  const [expanded, setExpanded] = useState(false)

  // Close the expanded overlay on Escape so keyboard users aren't trapped.
  useEffect(() => {
    if (!expanded) return
    const onKey = (e) => { if (e.key === 'Escape') setExpanded(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])

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
      // Contain the absolute-positioned expanded overlay so it anchors here
      // and doesn't leak out to the root. The collapsed bar itself doesn't
      // clip, so we only clip on the summary row.
      position: 'relative',
      zIndex: 5,
    }}>
      {/* Collapsed summary bar — always visible */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '9px 28px',
          cursor: 'pointer',
          gap: 14,
          userSelect: 'none',
          overflow: 'hidden',
        }}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--gold)',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>
          // Oracle Verdict
        </div>

        <div className="playfair" style={{
          flex: 1,
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 13,
          color: '#FFFFFF',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          minWidth: 0,
        }}>
          {ds.verdict}
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          flexShrink: 0,
        }}>
          {/* Confidence badge */}
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: confColor,
            border: `1px solid ${confColor}`,
            padding: '2px 7px',
            borderRadius: 2,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}>
            {ds.confidence}
          </div>

          {/* Numeric aggregate — clear, unambiguous */}
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--gold)',
            fontWeight: 500,
          }}>
            {ds.verdict_stance?.toFixed(2) ?? '—'}
            <span style={{
              fontSize: 9,
              color: '#FFFFFF',
              marginLeft: 3,
              fontWeight: 400,
            }}>
              stance
            </span>
          </div>

          {/* Ensemble robustness badge */}
          {ensembleResult && (() => {
            const n = ensembleResult.ensemble_size || 0
            const ratio = ensembleResult.agreement_ratio || 0
            const agree = Math.round(ratio * n)
            const badgeColor = ratio >= 0.9 ? '#8FD18F' : ratio >= 0.6 ? '#F5D98A' : '#E09A9A'
            return (
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: badgeColor,
                border: `1px solid ${badgeColor}`,
                padding: '2px 7px',
                borderRadius: 2,
                letterSpacing: '0.06em',
              }}>
                {agree}/{n} agree
              </div>
            )
          })()}

          {/* Stance indicator */}
          <div style={{
            width: 78,
            position: 'relative',
          }}>
            <div style={{
              height: 3,
              background: '#6a6a60',
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
              boxShadow: '0 0 6px rgba(245,217,138,0.5)',
            }} />
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginTop: 4,
            }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#FFFFFF' }}>
                {lowLabel}
              </span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: '#FFFFFF' }}>
                {highLabel}
              </span>
            </div>
          </div>

          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: '#FFFFFF',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 0.3s ease',
          }}>▾</div>
        </div>
      </div>

      {/* Expanded detail — overlay anchored to the bottom of the viewport so it
          always has room to scroll regardless of how tall the main layout
          (Header, Stage/Arena, OracleMethod, StanceGraph) is. Without this
          the panel's natural position can be pushed below the fold on shorter
          windows, stranding the Ensemble Details / Backtest sections out of
          reach. Using position: absolute and anchoring to bottom: 100% puts
          it above the collapsed bar; we keep overflow-y auto and cap height
          at 75vh so it fills most of the viewport but never overflows it. */}
      {expanded && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            bottom: '100%',
            maxHeight: '75vh',
            overflowY: 'auto',
            overflowX: 'hidden',
            background: 'var(--surface-warm)',
            borderTop: '1px solid var(--border)',
            borderBottom: '1px solid var(--border)',
            boxShadow: '0 -8px 24px rgba(0,0,0,0.35)',
            // Stop wheel/touch scrolls from bubbling up and scrolling the
            // (overflow-hidden) body; also avoids the main flex row
            // intercepting them.
            overscrollBehavior: 'contain',
          }}
          // Clicks inside the expanded region must not toggle collapse.
          onClick={(e) => e.stopPropagation()}
        >
          <div className="wrap-anywhere" style={{
            padding: '14px 28px 20px',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '12px 24px',
          }}>
          {/* Full verdict — always wraps, never truncated */}
          <div style={{ gridColumn: '1 / -1' }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--gold)',
              marginBottom: 6,
            }}>Full Verdict</div>
            <div className="playfair" style={{
              fontFamily: 'var(--font-display)',
              fontStyle: 'italic',
              fontSize: 14,
              color: '#FFFFFF',
            }}>
              {ds.verdict}
            </div>
            {ds.confidence_rationale && (
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 400,
                fontSize: 11,
                color: '#FFFFFF',
                marginTop: 6,
                opacity: 0.9,
              }}>{ds.confidence_rationale}</div>
            )}
          </div>
          {/* Arguments For */}
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#8FD18F',
              marginBottom: 7,
            }}>Arguments For</div>
            {ds.arguments_for?.map((arg, i) => (
              <ArgumentCard key={i} arg={arg} direction="for" />
            ))}
            {(!ds.arguments_for || ds.arguments_for.length === 0) && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#FFFFFF' }}>
                No strong arguments recorded
              </div>
            )}
          </div>

          {/* Arguments Against */}
          <div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#E09A9A',
              marginBottom: 7,
            }}>Arguments Against</div>
            {ds.arguments_against?.map((arg, i) => (
              <ArgumentCard key={i} arg={arg} direction="against" />
            ))}
            {(!ds.arguments_against || ds.arguments_against.length === 0) && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: '#FFFFFF' }}>
                No strong arguments recorded
              </div>
            )}
          </div>

          {/* Key Risk */}
          {ds.key_risk && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#E09D8A',
                marginBottom: 4,
              }}>Key Risk</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 400,
                fontSize: 11,
                color: '#FFFFFF',
                lineHeight: 1.6,
              }}>{ds.key_risk}</div>
            </div>
          )}

          {/* Influence Narrative */}
          {ds.influence_narrative && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--gold)',
                marginBottom: 4,
              }}>How Agents Influenced Each Other</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 400,
                fontSize: 11,
                color: '#FFFFFF',
                lineHeight: 1.6,
              }}>{ds.influence_narrative}</div>
            </div>
          )}

          {/* What Could Change */}
          {ds.what_could_change && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#FFFFFF',
                marginBottom: 4,
              }}>What Could Change the Outcome</div>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontWeight: 400,
                fontSize: 11,
                color: '#FFFFFF',
                lineHeight: 1.6,
              }}>{ds.what_could_change}</div>
            </div>
          )}

          {/* Actionable Takeaways */}
          {ds.actionable_takeaways?.length > 0 && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--gold)',
                marginBottom: 5,
              }}>Before You Decide — Do This</div>
              {ds.actionable_takeaways.map((t, i) => (
                <div key={i} style={{
                  display: 'flex',
                  gap: 8,
                  padding: '4px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--gold)',
                    flexShrink: 0,
                  }}>{i + 1}.</span>
                  <span style={{
                    fontFamily: 'var(--font-ui)',
                    fontWeight: 400,
                    fontSize: 11,
                    color: '#FFFFFF',
                    lineHeight: 1.6,
                  }}>{t}</span>
                </div>
              ))}
            </div>
          )}

          {/* Grounded Reasoning Rates — Step 7 */}
          {ds.grounded_reasoning_rates && Object.keys(ds.grounded_reasoning_rates).length > 0 && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--text-ui)',
                marginBottom: 6,
              }}>Document Citation Rates</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {Object.entries(ds.grounded_reasoning_rates).map(([agentId, rate]) => {
                  const isLow = rate < 0.20
                  const color = isLow ? '#9B6A6A' : '#6A9B6A'
                  return (
                    <div key={agentId} style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 9,
                      color,
                      border: `1px solid ${color}`,
                      padding: '2px 8px',
                      borderRadius: 2,
                    }}>
                      {agentId}: {Math.round(rate * 100)}%
                      {isLow && <span style={{ marginLeft: 4, fontSize: 8, opacity: 0.7 }}>low</span>}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Ensemble Details — Step 6 */}
          {ensembleResult && ensembleResult.ensemble_size > 1 && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#6A9B6A',
                marginBottom: 6,
              }}>Ensemble Robustness ({ensembleResult.ensemble_size} runs)</div>

              {/* Per-run aggregates */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                {(ensembleResult.aggregate_distribution || []).map((agg, i) => {
                  const conf = ensembleResult.confidence_distribution?.[i] || '?'
                  const confC = confidenceColors[conf] || '#4a4a44'
                  return (
                    <div key={i} style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: 9,
                      color: 'var(--text-ui)',
                      border: '1px solid #2a2a25',
                      padding: '3px 8px',
                      borderRadius: 2,
                    }}>
                      Run {i + 1}: {agg.toFixed(2)}{' '}
                      <span style={{ color: confC, fontSize: 8 }}>{conf}</span>
                    </div>
                  )
                })}
              </div>

              {/* Robust herd moments */}
              {ensembleResult.robust_herd_moments?.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 8,
                    color: '#C08878',
                    marginBottom: 3,
                  }}>Robust herd moments (appeared in ≥2 runs):</div>
                  {ensembleResult.robust_herd_moments.map((m, i) => (
                    <div key={i} style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 9,
                      color: 'var(--text-ui)',
                      padding: '2px 0',
                    }}>⚠ {m}</div>
                  ))}
                </div>
              )}

              {/* Noisy herd moments */}
              {ensembleResult.noisy_herd_moments?.length > 0 && (
                <div>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 8,
                    color: 'var(--text-muted)',
                    marginBottom: 3,
                  }}>Noisy herd moments (only 1 run — may be noise):</div>
                  {ensembleResult.noisy_herd_moments.map((m, i) => (
                    <div key={i} style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: 9,
                      color: 'var(--text-muted)',
                      padding: '2px 0',
                      opacity: 0.7,
                    }}>? {m}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Backtest Comparison — Step 8 */}
          {backtestResult && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 8,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: '#C08878',
                marginBottom: 8,
              }}>Ground Truth Comparison</div>

              <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                {/* Predicted vs Actual */}
                <div style={{
                  flex: 1,
                  padding: '8px 10px',
                  border: '1px solid #2a2a25',
                  borderRadius: 3,
                }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)', marginBottom: 4 }}>
                    Predicted
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--text-primary)' }}>
                    {backtestResult.predicted_aggregate?.toFixed(2) ?? '—'}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: confidenceColors[backtestResult.predicted_confidence] || '#4a4a44', marginTop: 2 }}>
                    {backtestResult.predicted_confidence}
                  </div>
                </div>

                <div style={{
                  flex: 1,
                  padding: '8px 10px',
                  border: '1px solid #2a2a25',
                  borderRadius: 3,
                }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)', marginBottom: 4 }}>
                    Actual
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, color: 'var(--text-primary)' }}>
                    {backtestResult.actual_aggregate?.toFixed(2) ?? '—'}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: confidenceColors[backtestResult.actual_confidence] || '#4a4a44', marginTop: 2 }}>
                    {backtestResult.actual_confidence}
                  </div>
                </div>
              </div>

              {/* Calibration scores */}
              {backtestResult.calibration && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    color: backtestResult.calibration.direction_correct ? '#6A9B6A' : '#9B6A6A',
                    border: `1px solid ${backtestResult.calibration.direction_correct ? '#6A9B6A' : '#9B6A6A'}`,
                    padding: '2px 8px',
                    borderRadius: 2,
                  }}>
                    Direction: {backtestResult.calibration.direction_correct ? '✓ correct' : '✗ wrong'}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    color: backtestResult.calibration.aggregate_error < 0.15 ? '#6A9B6A' : '#C08878',
                    border: `1px solid ${backtestResult.calibration.aggregate_error < 0.15 ? '#6A9B6A' : '#C08878'}`,
                    padding: '2px 8px',
                    borderRadius: 2,
                  }}>
                    Error: {backtestResult.calibration.aggregate_error?.toFixed(3)}
                  </div>
                  <div style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 9,
                    color: backtestResult.calibration.confidence_match ? '#6A9B6A' : '#9B6A6A',
                    border: `1px solid ${backtestResult.calibration.confidence_match ? '#6A9B6A' : '#9B6A6A'}`,
                    padding: '2px 8px',
                    borderRadius: 2,
                  }}>
                    Confidence: {backtestResult.calibration.confidence_match ? '✓ match' : '✗ mismatch'}
                  </div>
                </div>
              )}
            </div>
          )}
          </div>
        </div>
      )}
    </div>
  )
}
