export default function Header({ scenarioName, tick, run, progressPercent, onRestart, paused, onTogglePause, totalTicks, onHome }) {
  const tickStr = String(tick).padStart(2, '0')
  const runStr  = String(run).padStart(2, '0')
  const totalStr = String(totalTicks || 20).padStart(2, '0')

  return (
    <>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 28px 12px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        {/* Logo + Home */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontStyle: 'italic',
            fontSize: 22,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: '#FFFFFF',
            lineHeight: 1.35,
          }}>
            Pythia
            <span style={{
              fontStyle: 'normal',
              fontFamily: 'var(--font-ui)',
              fontWeight: 400,
              fontSize: 13,
              color: 'var(--gold)',
              letterSpacing: '0.04em',
            }}>◈ ORACLE</span>
          </div>
          {onHome && (
            <button
              type="button"
              aria-label="Return to home"
              title="Return to home — start a new run"
              onClick={onHome}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                letterSpacing: '0.10em',
                textTransform: 'uppercase',
                color: 'var(--gold)',
                background: 'rgba(245,217,138,0.10)',
                border: '1px solid var(--gold)',
                padding: '5px 11px',
                cursor: 'pointer',
                borderRadius: 3,
                lineHeight: 1.4,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(245,217,138,0.18)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(245,217,138,0.10)'
              }}
            >⌂ Home</button>
          )}
        </div>

        {/* Scenario */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 500,
            fontSize: 10,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: '#FFFFFF',
            lineHeight: 1.5,
          }}>Active Scenario</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 500,
            fontSize: 14,
            color: '#FFFFFF',
            marginTop: 3,
            lineHeight: 1.5,
          }}>{scenarioName}</div>
        </div>

        {/* Tick + Restart */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            type="button"
            aria-label={paused ? 'Resume simulation' : 'Pause simulation'}
            onClick={onTogglePause}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--gold)',
              background: 'none',
              border: '1px solid var(--gold)',
              padding: '4px 9px',
              cursor: 'pointer',
              lineHeight: 1.2,
            }}
          >{paused ? '▶' : '▐▐'}</button>
          <button
            type="button"
            aria-label="Restart simulation"
            onClick={onRestart}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--gold)',
              background: 'none',
              border: '1px solid var(--gold)',
              padding: '5px 11px',
              cursor: 'pointer',
              lineHeight: 1.4,
            }}
          >↺ Restart</button>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: '#FFFFFF',
              letterSpacing: '0.12em',
              lineHeight: 1.4,
            }}>TICK</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 20,
              fontWeight: 300,
              color: '#FFFFFF',
              letterSpacing: '-0.03em',
              lineHeight: 1.15,
              marginTop: 2,
            }}>{tickStr} / {totalStr}</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--gold)',
              letterSpacing: '0.1em',
              marginTop: 2,
              lineHeight: 1.4,
            }}>RUN · {runStr}</div>
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div style={{ height: 2, background: '#3a3a32', flexShrink: 0 }}>
        <div style={{
          height: '100%',
          background: 'var(--gold)',
          width: `${progressPercent}%`,
          transition: 'width 1s cubic-bezier(0.4,0,0.2,1)',
          boxShadow: '0 0 6px var(--gold)',
        }} />
      </div>
    </>
  )
}
