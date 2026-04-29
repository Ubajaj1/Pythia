import { useState, useMemo } from 'react'

// ── Named constants ──────────────────────────────────────────────────────────
// All visual tuning knobs are here, not buried in JSX.

const GRAPH_WIDTH = 500
const GRAPH_HEIGHT = 80
const GRAPH_PADDING = 6

// Aggregate line: thick, prominent — this is the headline signal
const AGGREGATE_LINE_WIDTH = 2.5
const AGGREGATE_LINE_COLOR = '#F5D98A'  // brighter gold — high contrast on dark background
const AGGREGATE_LINE_OPACITY = 1.0

// Per-agent lines: thin, faded — context, not focus
const AGENT_LINE_WIDTH = 1.15
const AGENT_LINE_OPACITY = 0.5

// Midline at 0.5 — the "neutral" divider
const MIDLINE_COLOR = '#6a6a60'
const MIDLINE_OPACITY = 0.9
const MIDLINE_DASH = '3,3'

// Y-axis range: stance is always 0–1
const STANCE_MIN = 0.0
const STANCE_MAX = 1.0

/**
 * StanceGraph — SVG polyline chart showing aggregate + per-agent stance over ticks.
 *
 * Used in single-run mode (API simulation, streaming simulation).
 * Oracle mode keeps AccuracyCurve (coherence across re-runs is the right signal there).
 *
 * Props:
 *   ticks: array of { tick, events: [{ agent_id, stance }], aggregate_stance }
 *   agents: array of { id, name, bias, color? }
 *   stanceSpectrum: array of 5 strings (labels for 0.0 → 1.0)
 *   currentTick: number — how far into the replay we are (for progressive reveal)
 */
export default function StanceGraph({ ticks, agents, stanceSpectrum, currentTick }) {
  const [showTooltip, setShowTooltip] = useState(false)

  const lowLabel = stanceSpectrum?.[0] || '0.0'
  const highLabel = stanceSpectrum?.[4] || '1.0'

  // Build polyline data from ticks, clipped to currentTick for progressive reveal
  const { aggregatePoints, agentLines } = useMemo(() => {
    if (!ticks?.length) return { aggregatePoints: '', agentLines: [] }

    const visibleTicks = ticks.filter(t => t.tick <= (currentTick || ticks.length))

    // Aggregate stance line
    const aggCoords = visibleTicks.map((t, i) => {
      const x = GRAPH_PADDING + (i / Math.max(visibleTicks.length - 1, 1)) * (GRAPH_WIDTH - GRAPH_PADDING * 2)
      const y = stanceToY(t.aggregate_stance)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })

    // Per-agent lines
    const agentMap = {}
    for (const t of visibleTicks) {
      for (const ev of (t.events || [])) {
        if (!agentMap[ev.agent_id]) agentMap[ev.agent_id] = []
        agentMap[ev.agent_id].push({ tick: t.tick, stance: ev.stance })
      }
    }

    const lines = (agents || []).map(agent => {
      const data = agentMap[agent.id] || []
      const coords = data.map((d, i) => {
        const x = GRAPH_PADDING + (i / Math.max(data.length - 1, 1)) * (GRAPH_WIDTH - GRAPH_PADDING * 2)
        const y = stanceToY(d.stance)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      return {
        id: agent.id,
        name: agent.name,
        color: agent.color || '#6a6a5a',
        points: coords.join(' '),
      }
    })

    return { aggregatePoints: aggCoords.join(' '), agentLines: lines }
  }, [ticks, agents, currentTick])

  // Current aggregate value for the big number display
  const currentAggregate = useMemo(() => {
    if (!ticks?.length) return null
    const visible = ticks.filter(t => t.tick <= (currentTick || ticks.length))
    return visible.length ? visible[visible.length - 1].aggregate_stance : null
  }, [ticks, currentTick])

  return (
    <footer style={{
      height: 62,
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 28px',
      gap: 16,
      flexShrink: 0,
    }}>
      <div
        style={{ position: 'relative', cursor: 'help' }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#FFFFFF',
          whiteSpace: 'nowrap',
          lineHeight: 1.55,
        }}>
          Stance<br />Trajectory
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--gold)', marginTop: 2 }}>ⓘ</div>
        {showTooltip && (
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            width: 230,
            background: '#1a1a17',
            border: '1px solid #6a6a60',
            padding: '7px 9px',
            fontSize: 10,
            color: '#FFFFFF',
            lineHeight: 1.55,
            zIndex: 10,
            pointerEvents: 'none',
            marginBottom: 6,
          }}>
            <strong style={{ color: AGGREGATE_LINE_COLOR }}>Gold line</strong> = aggregate stance.{' '}
            <span style={{ opacity: 0.85 }}>Faded</span> = individual agents.
          </div>
        )}
      </div>

      <div style={{ flex: 1, position: 'relative', height: 44 }}>
        {/* Y-axis labels */}
        <div style={{
          position: 'absolute', top: -2, left: 0,
          fontFamily: 'var(--font-mono)', fontSize: 8, color: '#FFFFFF',
        }}>{highLabel}</div>
        <div style={{
          position: 'absolute', bottom: -2, left: 0,
          fontFamily: 'var(--font-mono)', fontSize: 8, color: '#FFFFFF',
        }}>{lowLabel}</div>

        <svg
          viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
          preserveAspectRatio="none"
          style={{ width: '100%', height: '100%', overflow: 'visible' }}
        >
          <defs>
            <linearGradient id="stance-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={AGGREGATE_LINE_COLOR} stopOpacity="0.12" />
              <stop offset="100%" stopColor={AGGREGATE_LINE_COLOR} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Midline at 0.5 */}
          <line
            x1={GRAPH_PADDING} y1={stanceToY(0.5)}
            x2={GRAPH_WIDTH - GRAPH_PADDING} y2={stanceToY(0.5)}
            stroke={MIDLINE_COLOR}
            strokeOpacity={MIDLINE_OPACITY}
            strokeDasharray={MIDLINE_DASH}
            strokeWidth="0.5"
          />

          {/* Per-agent lines (behind aggregate) */}
          {agentLines.map(line => (
            <polyline
              key={line.id}
              points={line.points}
              fill="none"
              stroke={line.color}
              strokeWidth={AGENT_LINE_WIDTH}
              strokeOpacity={AGENT_LINE_OPACITY}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {/* Aggregate area fill */}
          {aggregatePoints && (
            <path
              d={buildAreaPath(aggregatePoints)}
              fill="url(#stance-grad)"
              stroke="none"
            />
          )}

          {/* Aggregate line */}
          {aggregatePoints && (
            <polyline
              points={aggregatePoints}
              fill="none"
              stroke={AGGREGATE_LINE_COLOR}
              strokeWidth={AGGREGATE_LINE_WIDTH}
              strokeOpacity={AGGREGATE_LINE_OPACITY}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}
        </svg>
      </div>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 20,
        fontWeight: 300,
        color: '#FFFFFF',
        letterSpacing: '-0.03em',
        whiteSpace: 'nowrap',
        minWidth: 46,
        textAlign: 'right',
      }}>
        {currentAggregate != null ? currentAggregate.toFixed(2) : '—'}
      </div>
    </footer>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function stanceToY(stance) {
  // Invert: stance 1.0 → top, 0.0 → bottom
  const clamped = Math.max(STANCE_MIN, Math.min(STANCE_MAX, stance))
  const normalized = (clamped - STANCE_MIN) / (STANCE_MAX - STANCE_MIN)
  return GRAPH_HEIGHT - GRAPH_PADDING - normalized * (GRAPH_HEIGHT - GRAPH_PADDING * 2)
}

function buildAreaPath(pointsStr) {
  if (!pointsStr) return ''
  const pairs = pointsStr.split(' ')
  const firstX = pairs[0]?.split(',')[0] || String(GRAPH_PADDING)
  const lastX = pairs[pairs.length - 1]?.split(',')[0] || String(GRAPH_PADDING)
  return `M ${firstX},${GRAPH_HEIGHT} L ${pointsStr} ${lastX},${GRAPH_HEIGHT} Z`
}
