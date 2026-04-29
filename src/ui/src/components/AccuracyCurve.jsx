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
      height: 130,
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '12px 28px',
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
          fontSize: 10,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: '#FFFFFF',
          whiteSpace: 'nowrap',
          lineHeight: 1.55,
        }}>
          Coherence<br />Score
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--gold)', marginTop: 3 }}>ⓘ</div>
        {showTooltip && (
          <div style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            width: 240,
            background: '#1a1a17',
            border: '1px solid #6a6a60',
            padding: '8px 10px',
            fontSize: 11,
            color: '#FFFFFF',
            lineHeight: 1.55,
            zIndex: 10,
            pointerEvents: 'none',
            marginBottom: 6,
          }}>
            Whether agent actions matched their stated reasoning — internal self-consistency.
          </div>
        )}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
        style={{ flex: 1, height: 100, overflow: 'visible' }}>
        <defs>
          <linearGradient id="acc-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F5D98A" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#F5D98A" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaD} fill="url(#acc-grad)" stroke="none" />
        <polyline points={linePoints} fill="none" stroke="#F5D98A"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 26,
        fontWeight: 300,
        color: '#FFFFFF',
        letterSpacing: '-0.03em',
        whiteSpace: 'nowrap',
      }}>
        {current != null ? Math.round(current) : '—'}
        <span style={{ fontSize: 12, color: '#FFFFFF', verticalAlign: 'super', marginLeft: 1 }}>%</span>
      </div>
    </footer>
  )
}
