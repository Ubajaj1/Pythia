import { useRef, useEffect, useState } from 'react'

const C_REST   = [58,  58,  56]
const C_ACTIVE = [200, 194, 185]
const C_PANIC  = [160, 72,  60]
const C_BULLISH = [106, 155, 106]

function lerpRGB(a, b, t) {
  return a.map((v, i) => Math.round(v + (b[i] - v) * t))
}

function crowdConfig(stateIdx, W, H) {
  const cx = W / 2, cy = H / 2
  return [
    { attr: 0,       cx, cy,          spd: 0.28, ct: 0,    chaos: 0,   panic: false },
    { attr: 0.004,   cx, cy,          spd: 0.55, ct: 0.42, chaos: 0,   panic: false },
    { attr: 0.009,   cx, cy: cy*0.85, spd: 0.75, ct: 0.72, chaos: 0.12,panic: false },
    { attr: 0.022,   cx, cy: cy*0.65, spd: 0.35, ct: 0.92, chaos: 0,   panic: false },
    { attr: -0.006,  cx, cy,          spd: 2.6,  ct: 0.55, chaos: 1.8, panic: true  },
  ][stateIdx] ?? { attr: 0, cx, cy, spd: 0.3, ct: 0, chaos: 0, panic: false }
}

function initParticles(W, H, count = 290) {
  return Array.from({ length: count }, () => ({
    x:  Math.random() * W,
    y:  Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    sz: 2.2 + Math.random() * 1.4,
    ct: 0,
  }))
}

export default function Arena({ crowdStateIndex, crowdStateName, aggregateStance }) {
  const canvasRef  = useRef(null)
  const stateRef   = useRef({ particles: [], crowdStateIndex: 0, aggregateStance: 0.5 })
  const rafRef     = useRef(null)
  const [showLegend, setShowLegend] = useState(false)

  useEffect(() => {
    stateRef.current.crowdStateIndex = crowdStateIndex
  }, [crowdStateIndex])

  useEffect(() => {
    if (aggregateStance != null) {
      stateRef.current.aggregateStance = aggregateStance
    }
  }, [aggregateStance])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    function resize() {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      if (!W || !H) return
      const dpr = window.devicePixelRatio || 1
      canvas.width  = W * dpr
      canvas.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      stateRef.current.particles = initParticles(W, H)
    }

    function frame() {
      const W = canvas.offsetWidth
      const H = canvas.offsetHeight
      if (!W || !H) { rafRef.current = requestAnimationFrame(frame); return }

      const cfg = crowdConfig(stateRef.current.crowdStateIndex, W, H)
      ctx.clearRect(0, 0, W, H)

      stateRef.current.particles.forEach(p => {
        if (cfg.attr !== 0) {
          p.vx += (cfg.cx - p.x) * cfg.attr
          p.vy += (cfg.cy - p.y) * cfg.attr
        }
        if (cfg.chaos > 0) {
          p.vx += (Math.random() - 0.5) * cfg.chaos
          p.vy += (Math.random() - 0.5) * cfg.chaos
        }
        const spd = Math.hypot(p.vx, p.vy)
        if (spd > cfg.spd) { p.vx = p.vx / spd * cfg.spd; p.vy = p.vy / spd * cfg.spd }
        p.vx *= 0.98; p.vy *= 0.98
        p.x += p.vx;  p.y += p.vy
        if (p.x < 0) p.x = W; if (p.x > W) p.x = 0
        if (p.y < 0) p.y = H; if (p.y > H) p.y = 0
        p.ct += (cfg.ct - p.ct) * 0.018

        // Use aggregate stance to modulate color intensity
        // Extreme stances (near 0 or 1) = more active colors
        const agg = stateRef.current.aggregateStance
        const extremity = Math.abs(agg - 0.5) * 2  // 0 at center, 1 at extremes
        const colorBlend = Math.max(p.ct, extremity * 0.6)

        const rgb = cfg.panic
          ? lerpRGB(C_REST, C_PANIC, colorBlend)
          : agg < 0.35
            ? lerpRGB(C_REST, C_PANIC, colorBlend * 0.6)
            : agg > 0.65
              ? lerpRGB(C_REST, C_BULLISH, colorBlend * 0.6)
              : lerpRGB(C_REST, C_ACTIVE, colorBlend)
        const alpha = 0.38 + colorBlend * 0.48
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.sz, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`
        ctx.fill()
      })

      rafRef.current = requestAnimationFrame(frame)
    }

    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    resize()
    rafRef.current = requestAnimationFrame(frame)

    return () => {
      ro.disconnect()
      cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      <div style={{
        position: 'absolute',
        bottom: 14,
        left: 0, right: 0,
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
        fontSize: 8.5,
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        color: 'var(--text-ui)',
        pointerEvents: 'none',
      }}>
        {crowdStateName}
        {aggregateStance != null && (
          <span style={{ marginLeft: 8, color: 'var(--gold-dim)' }}>
            · {(aggregateStance * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Info button */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          cursor: 'pointer',
          zIndex: 5,
        }}
        onClick={() => setShowLegend(s => !s)}
      >
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--gold-dim)',
          opacity: 0.6,
        }}>ⓘ</span>
      </div>

      {/* Legend overlay */}
      {showLegend && (
        <div style={{
          position: 'absolute',
          top: 28,
          right: 10,
          width: 220,
          background: 'rgba(13,13,11,0.95)',
          border: '1px solid #2a2a25',
          borderRadius: 3,
          padding: '10px 12px',
          zIndex: 10,
          pointerEvents: 'auto',
        }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 8,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--gold-ui)',
            marginBottom: 8,
          }}>Crowd Dynamics</div>
          <div style={{ fontFamily: 'var(--font-ui)', fontSize: 9, color: 'var(--text-ui)', lineHeight: 1.7 }}>
            Each particle represents a segment of the broader population affected by this decision.
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgb(160,72,60)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)' }}>
                Red — crowd leans against (bearish/oppose)
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgb(200,194,185)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)' }}>
                Neutral — undecided / balanced
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'rgb(106,155,106)' }} />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: 'var(--text-muted)' }}>
                Green — crowd leans for (bullish/support)
              </span>
            </div>
          </div>
          <div style={{ marginTop: 8, fontFamily: 'var(--font-ui)', fontSize: 8, color: '#3a3a35', lineHeight: 1.6 }}>
            Clustering = consensus forming. Scattering = polarization. Speed = intensity of debate.
          </div>
        </div>
      )}
    </div>
  )
}
