import { useEffect, useRef } from 'react'

const CIRC = 2 * Math.PI * 18   // r=18, circumference ≈ 113.1

function ProtagNode({ protagonist, state, delay }) {
  const dotRef = useRef(null)

  // Flash animation on return from temple
  useEffect(() => {
    if (!state.returning || !dotRef.current) return
    dotRef.current.animate([
      { boxShadow: '0 0 0 0 rgba(196,169,106,0)' },
      { boxShadow: '0 0 28px 10px rgba(196,169,106,0.55)' },
      { boxShadow: '0 0 8px 3px rgba(196,169,106,0.18)' },
    ], { duration: 1400, fill: 'forwards' })
  }, [state.returning])

  const visible  = state.spawned
  const inTemple = state.inTemple
  const conf     = state.conf
  const dashOffset = CIRC * (1 - conf / 100)

  const opacity   = inTemple ? 0.25 : 1
  const translateX = inTemple ? 16 : 0

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '10px 0',
      borderBottom: '1px solid rgba(255,255,255,0.028)',
      opacity: visible ? opacity : 0,
      transform: `translateX(${visible ? translateX : -12}px)`,
      transition: `opacity 0.7s ease ${delay}s, transform 0.7s ease ${delay}s`,
    }}>
      {/* Ring + Dot */}
      <div style={{ position: 'relative', width: 42, height: 42, flexShrink: 0 }}>
        <svg style={{ position: 'absolute', inset: 0, width: 42, height: 42 }}
          viewBox="0 0 42 42">
          <circle cx="21" cy="21" r="18" fill="none"
            stroke="var(--text-dim)" strokeWidth="1.5" />
          <circle cx="21" cy="21" r="18" fill="none"
            stroke={inTemple ? '#5A4A28' : protagonist.color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={dashOffset}
            style={{
              transformOrigin: '21px 21px',
              transform: 'rotate(-90deg)',
              transition: 'stroke-dashoffset 1.1s cubic-bezier(0.4,0,0.2,1), stroke 0.9s ease',
            }}
          />
        </svg>
        <div
          ref={dotRef}
          style={{
            position: 'absolute',
            inset: 0,
            margin: 'auto',
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: protagonist.color,
            opacity: visible ? 1 : 0,
            transition: 'opacity 0.9s ease',
            animation: visible && !inTemple ? `dot-pulse 2.8s ease-in-out ${delay}s infinite` : 'none',
            '--glow': protagonist.glow,
          }}
        />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 600,
          fontSize: 11.5,
          color: 'var(--text-primary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>{protagonist.name}</div>
        <div style={{
          fontFamily: 'var(--font-ui)',
          fontWeight: 300,
          fontSize: 9.5,
          color: 'var(--gold)',
          marginTop: 2,
          opacity: visible ? 1 : 0,
          transition: 'opacity 1.2s ease 0.5s',
        }}>{protagonist.trait}</div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          color: 'var(--text-muted)',
          marginTop: 3,
        }}>{visible ? `${Math.round(conf)}%` : '—'}</div>
      </div>
    </div>
  )
}

export default function Stage({ protagonists, protoStates }) {
  return (
    <div style={{
      width: 210,
      flexShrink: 0,
      borderRight: '1px solid var(--border)',
      padding: '20px 18px',
      overflowY: 'auto',
    }}>
      <style>{`
        @keyframes dot-pulse {
          0%, 100% { box-shadow: 0 0 6px 2px var(--glow); }
          50%       { box-shadow: 0 0 18px 7px var(--glow); }
        }
      `}</style>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: 'var(--text-ui)',
        marginBottom: 18,
      }}>// The Stage</div>

      {protagonists.map((p, i) => (
        <ProtagNode
          key={p.id}
          protagonist={p}
          state={protoStates[i]}
          delay={i * 0.1}
        />
      ))}
    </div>
  )
}
