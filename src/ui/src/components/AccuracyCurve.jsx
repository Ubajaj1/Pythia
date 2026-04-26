import { useState } from 'react'

export default function AccuracyCurve({ history }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const W = 500, H = 32, PAD = 6
  const MIN_ACC = 30, MAX_ACC = 100

  const coords = history.map((acc, i) => {
    const x = PAD + (i / Math.max(history.length - 1, 1)) * (W - PAD * 2)
    const y = H - PAD - ((acc - MIN_ACC) / (MAX_ACC - MIN_ACC)) * (H - PAD * 2)
    return [x, y]
  })

  const linePoints = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const lastX = coords[coords.length - 1]?.[0] ?? PAD
  const areaD = `M ${PAD},${H} L ${linePoints.replace(',', ' ')} ${lastX.toFixed(1)},${H} Z`
  const current = history[history.length - 1]

  return (
    <footer style={{
      height: 64,
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 28px',
      gap: 18,
      flexShrink: 0,
    }}>
      <div
        style={{ position: 'relative', cursor: 'help' }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 8,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--text-ui)',
          whiteSpace: 'nowrap',
          lineHeight: 1.6,
        }}>
          Coherence<br />Score
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--gold-dim)', marginTop: 2 }}>ⓘ</div>
        {showTooltip && (
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            width: 220,
            background: '#1a1a17',
            border: '1px solid #2a2a25',
            padding: '8px 10px',
            fontSize: 10,
            color: '#8a8a7a',
            lineHeight: 1.6,
            zIndex: 10,
            pointerEvents: 'none',
            marginBottom: 6,
          }}>
            Measures whether each agent's actions matched their stated reasoning — internal self-consistency, not a comparison to real-world outcomes.
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
        style={{ flex: 1, height: 32, overflow: 'visible' }}>
        <defs>
          <linearGradient id="acc-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#C4A96A" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#C4A96A" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#acc-grad)" stroke="none" />
        <polyline points={linePoints} fill="none" stroke="#A88C52"
          strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 20,
        fontWeight: 300,
        color: 'var(--text-primary)',
        letterSpacing: '-0.03em',
        whiteSpace: 'nowrap',
      }}>
        {current != null ? Math.round(current) : '—'}
        <span style={{ fontSize: 9, color: 'var(--text-muted)', verticalAlign: 'super', marginLeft: 1 }}>%</span>
      </div>
    </footer>
  )
}
