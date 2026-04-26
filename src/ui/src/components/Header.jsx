export default function Header({ scenarioName, tick, run, progressPercent, onRestart, paused, onTogglePause }) {
  const tickStr = String(tick).padStart(2, '0')
  const runStr  = String(run).padStart(2, '0')

  return (
    <>
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '18px 28px 14px',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'var(--text-primary)',
        }}>
          Pythia
          <span style={{
            fontStyle: 'normal',
            fontFamily: 'var(--font-ui)',
            fontWeight: 300,
            fontSize: 14,
            color: 'var(--gold)',
            letterSpacing: '0.04em',
          }}>◈ ORACLE</span>
        </div>

        {/* Scenario */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 300,
            fontSize: 9,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--text-ui)',
          }}>Active Scenario</div>
          <div style={{
            fontFamily: 'var(--font-ui)',
            fontWeight: 500,
            fontSize: 13,
            color: 'var(--text-primary)',
            marginTop: 3,
          }}>{scenarioName}</div>
        </div>

        {/* Tick + Restart */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <button
            type="button"
            aria-label={paused ? 'Resume simulation' : 'Pause simulation'}
            onClick={onTogglePause}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--gold-ui)',
              background: 'none',
              border: '1px solid var(--gold-ui)',
              padding: '5px 10px',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >{paused ? '▶' : '▐▐'}</button>
          <button
            type="button"
            aria-label="Restart simulation"
            onClick={onRestart}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--gold-ui)',
              background: 'none',
              border: '1px solid var(--gold-ui)',
              padding: '5px 12px',
              cursor: 'pointer',
            }}
          >↺ Restart</button>

          <div style={{ textAlign: 'right' }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--text-muted)',
              letterSpacing: '0.12em',
            }}>TICK</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 22,
              fontWeight: 300,
              color: 'var(--text-primary)',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              marginTop: 2,
            }}>{tickStr} / 20</div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              color: 'var(--gold-dim)',
              letterSpacing: '0.1em',
              marginTop: 2,
            }}>RUN · {runStr}</div>
          </div>
        </div>
      </header>

      {/* Progress bar */}
      <div style={{ height: 1, background: 'var(--text-dim)', flexShrink: 0 }}>
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
