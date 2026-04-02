import { useEffect, useState } from 'react'

function TypewriterText({ lines }) {
  const [displayed, setDisplayed] = useState('')
  const fullText = lines.join(' ')

  useEffect(() => {
    setDisplayed('')
    let i = 0
    const id = setInterval(() => {
      if (i >= fullText.length) { clearInterval(id); return }
      setDisplayed(fullText.slice(0, i + 1))
      i++
    }, 44)
    return () => clearInterval(id)
  }, [fullText])

  return (
    <div style={{
      fontFamily: 'var(--font-mono)',
      fontSize: 8.5,
      color: 'var(--text-muted)',
      textAlign: 'center',
      lineHeight: 1.9,
      letterSpacing: '0.02em',
      minHeight: 36,
    }}>{displayed}</div>
  )
}

export default function Temple({ protagonist, amendment }) {
  const active = protagonist !== null

  return (
    <div style={{
      width: 190,
      flexShrink: 0,
      borderLeft: '1px solid var(--border)',
      background: 'var(--surface-warm)',
      padding: '20px 16px',
      position: 'relative',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Ambient glow */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(ellipse 80% 50% at 50% 100%, rgba(196,169,106,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      <style>{`
        @keyframes temple-spin { to { transform: rotate(360deg); } }
      `}</style>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 8,
        letterSpacing: '0.18em',
        textTransform: 'uppercase',
        color: 'var(--gold-ui)',
        marginBottom: 18,
        flexShrink: 0,
      }}>// Temple of Learning</div>

      {/* Idle */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        opacity: active ? 0 : 1,
        transition: 'opacity 0.5s ease',
        position: active ? 'absolute' : 'relative',
        pointerEvents: 'none',
      }}>
        <div style={{ width: 24, height: 1, background: 'var(--text-muted)' }} />
        <div style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 11,
          color: 'var(--text-ui)',
          textAlign: 'center',
          lineHeight: 1.8,
        }}>The oracle<br />awaits the<br />fallen</div>
        <div style={{ width: 24, height: 1, background: 'var(--text-muted)' }} />
      </div>

      {/* Active */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        opacity: active ? 1 : 0,
        transform: active ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.7s ease, transform 0.7s ease',
      }}>
        {protagonist && (
          <>
            <div style={{ width: 44, height: 44, position: 'relative' }}>
              <svg viewBox="0 0 44 44" style={{ width: 44, height: 44, animation: 'temple-spin 3.5s linear infinite' }}>
                <circle cx="22" cy="22" r="17" fill="none"
                  stroke="var(--gold)" strokeWidth="1"
                  strokeLinecap="round"
                  strokeDasharray="90 20" opacity="0.8" />
              </svg>
              <div style={{
                position: 'absolute',
                inset: 0,
                margin: 'auto',
                width: 20,
                height: 20,
                borderRadius: '50%',
                background: protagonist.color,
              }} />
            </div>

            <div style={{
              fontFamily: 'var(--font-ui)',
              fontWeight: 500,
              fontSize: 11,
              color: 'var(--gold)',
              letterSpacing: '0.02em',
            }}>{protagonist.name}</div>

            <TypewriterText key={protagonist.id} lines={amendment} />
          </>
        )}
      </div>
    </div>
  )
}
