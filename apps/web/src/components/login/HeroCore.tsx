/**
 * HeroCore — animated centerpiece aligned to the particle hexagon.
 *
 * The hexagon outer ring is R=1.0 world units at z=0; camera is fov 55 at
 * z=5 → screen radius = innerHeight / (2 * 5 * tan(27.5°)) = innerHeight / 5.207.
 * Overlay is sized in exact pixels so guides/blips/orbits sit ON the rings.
 *
 * Layers:
 *   · radar sweep that eases toward the cursor, then resumes auto-rotation (L2)
 *   · ring blips; one occasionally turns RED (incident) and the core ACKs it (L1)
 *   · orbiting provider dots (multi-cloud)
 *   · mini log ticker under the core (L4)
 *   · breathing core + halo
 * Honors prefers-reduced-motion (static rings/dots/text).
 */
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimationFrame, useMotionValue, useReducedMotion } from 'framer-motion'

// world→screen: 2R / (2·z·tan(fov/2)) of viewport height, R=1, z=5, fov=55
const HEX_SIZE_FRACTION = 2 / (2 * 5 * Math.tan((55 / 2) * (Math.PI / 180))) // ≈ 0.384

function useHexSize(): number {
  const calc = () => Math.round(window.innerHeight * HEX_SIZE_FRACTION)
  const [size, setSize] = useState(calc)
  useEffect(() => {
    const onResize = () => setSize(calc())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return size
}

const RING = 1.0
const RING_INNER = 0.62

const BLIP_ANGLES = [18, 78, 142, 203, 262, 322]
const BLIP_DELAYS = [0, 1.2, 2.4, 3.1, 4, 4.8]
/** the 142° blip doubles as the incident probe (L1) */
const INCIDENT_INDEX = 2

const PROVIDERS = [
  { color: '#4285F4', label: 'GCP', frac: RING * 0.97, dur: 20, phase: 0, reverse: false },
  { color: '#8b5cf6', label: 'Azure', frac: RING_INNER, dur: 14, phase: 140, reverse: true },
  { color: '#f59e0b', label: 'AWS', frac: RING * 0.97, dur: 28, phase: 210, reverse: true },
]

const TICKER_POOL = [
  '▲ OOMKilled todo-backend-7b68 → restarted',
  '✓ RCA complete · confidence 92%',
  '⟳ argocd sync gcp-todo-app · ok',
  '▲ p99 latency 480ms on checkout',
  '✓ pod restart approved via HITL',
  '▲ P0 anomaly flagged · 34.9.192.101',
  '✓ runbook matched: CrashLoopBackOff',
]

export default function HeroCore() {
  const reduced = useReducedMotion()
  const size = useHexSize()
  const r = size / 2

  // ── L2: cursor-aware radar ──
  const sweep = useMotionValue(0)
  const lastMove = useRef(0)
  const mouseAngle = useRef(0)
  useEffect(() => {
    if (reduced) return
    const onMove = (e: MouseEvent) => {
      const dx = e.clientX - window.innerWidth / 2
      const dy = e.clientY - window.innerHeight / 2
      if (Math.hypot(dx, dy) < 40) return
      mouseAngle.current = (Math.atan2(dy, dx) * 180) / Math.PI
      lastMove.current = performance.now()
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [reduced])

  useAnimationFrame((_, delta) => {
    if (reduced) return
    const sinceMove = performance.now() - lastMove.current
    if (sinceMove < 2200) {
      // ease toward the cursor angle (shortest arc)
      const target = mouseAngle.current
      let diff = ((target - sweep.get()) % 360 + 540) % 360 - 180
      sweep.set(sweep.get() + diff * Math.min(1, delta * 6))
    } else {
      sweep.set(sweep.get() + delta * 51) // auto sweep ≈ 7s/rev
    }
  })

  // ── L1: incident blip → core ack cycle ──
  const [ack, setAck] = useState(0)
  useEffect(() => {
    if (reduced) return
    let flashT: ReturnType<typeof setTimeout>
    const iv = setInterval(() => {
      flashT = setTimeout(() => setAck((n) => n + 1), 550)
    }, 9000)
    return () => { clearInterval(iv); clearTimeout(flashT) }
  }, [reduced])

  // ── L4: mini log ticker ──
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (reduced) return
    const iv = setInterval(() => setTick((n) => n + 1), 2400)
    return () => clearInterval(iv)
  }, [reduced])
  const tickerLines = [0, 1, 2].map((off) => {
    const idx = (tick - off + TICKER_POOL.length * 4) % TICKER_POOL.length
    return { text: TICKER_POOL[idx], key: `${tick - off}-${idx}` }
  })

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute left-1/2 top-1/2 z-[12] hidden lg:block"
      style={{ width: size, height: size, transform: 'translate(-50%, -50%)' }}
    >
      <style>{`
        @keyframes heroOrbit { to { transform: rotate(360deg) } }
        @keyframes heroOrbitRev { to { transform: rotate(-360deg) } }
        @keyframes heroBlip { 0%, 78%, 100% { opacity: .12 } 8% { opacity: 1 } }
        @keyframes heroIncident {
          0%, 4% { background: #22d3ee; box-shadow: 0 0 8px rgba(34,211,238,.85); opacity: .14 }
          6% { background: #ef4444; box-shadow: 0 0 14px rgba(239,68,68,.95); opacity: 1; transform: scale(1.6) }
          9% { opacity: .35; transform: scale(1) }
          12% { background: #ef4444; box-shadow: 0 0 14px rgba(239,68,68,.95); opacity: 1; transform: scale(1.6) }
          18%, 100% { background: #22d3ee; box-shadow: 0 0 8px rgba(34,211,238,.85); opacity: .12; transform: scale(1) }
        }
      `}</style>

      {/* guides exactly on the two particle hexagons */}
      <div
        className="absolute rounded-full border border-cyan-400/10"
        style={{ inset: r * (1 - RING) }}
      />
      <div
        className="absolute rounded-full border border-cyan-400/[0.08]"
        style={{ inset: r * (1 - RING_INNER) }}
      />

      {/* radar sweep — cursor-aware (L2) */}
      {!reduced && (
        <div
          className="absolute inset-0 overflow-hidden rounded-full"
          style={{
            WebkitMaskImage: 'radial-gradient(circle, black 99%, transparent 100%)',
            maskImage: 'radial-gradient(circle, black 99%, transparent 100%)',
          }}
        >
          <motion.div
            className="absolute inset-0"
            style={{
              rotate: sweep,
              background:
                'conic-gradient(from 0deg, rgba(6,182,212,0.30) 0deg, rgba(6,182,212,0.06) 55deg, transparent 80deg)',
            }}
          />
        </div>
      )}

      {/* blips on the outer ring (one is the incident probe, L1) */}
      {BLIP_ANGLES.map((deg, i) => {
        const a = (deg * Math.PI) / 180
        const incident = i === INCIDENT_INDEX
        return (
          <span
            key={i}
            className="absolute h-1 w-1 rounded-full"
            style={{
              left: r + Math.cos(a) * r * 0.97 - 2,
              top: r - Math.sin(a) * r * 0.97 - 2,
              background: incident ? '#22d3ee' : '#22d3ee',
              boxShadow: '0 0 8px rgba(34,211,238,0.85)',
              opacity: reduced ? (incident ? 0.7 : 0.45) : undefined,
              animation:
                reduced
                  ? undefined
                  : incident
                    ? 'heroIncident 9s ease-in-out infinite'
                    : `heroBlip 7s ease-in-out ${BLIP_DELAYS[i]}s infinite`,
            }}
          />
        )
      })}

      {/* orbiting provider dots */}
      {PROVIDERS.map((p) =>
        reduced ? (
          <span
            key={p.label}
            className="absolute h-1.5 w-1.5 rounded-full"
            style={{
              left: r + Math.cos((p.phase * Math.PI) / 180) * r * p.frac - 3,
              top: r - Math.sin((p.phase * Math.PI) / 180) * r * p.frac - 3,
              background: p.color,
              boxShadow: `0 0 10px ${p.color}`,
            }}
          />
        ) : (
          <div
            key={p.label}
            className="absolute inset-0"
            style={{ animation: `${p.reverse ? 'heroOrbitRev' : 'heroOrbit'} ${p.dur}s linear infinite` }}
          >
            <span
              className="absolute h-1.5 w-1.5 rounded-full"
              style={{
                left: r + Math.cos((p.phase * Math.PI) / 180) * r * p.frac - 3,
                top: r - Math.sin((p.phase * Math.PI) / 180) * r * p.frac - 3,
                background: p.color,
                boxShadow: `0 0 10px ${p.color}`,
              }}
            />
          </div>
        ),
      )}

      {/* breathing core + halo, with ack flash (L1) */}
      <div
        className="absolute rounded-full border border-cyan-400/25"
        style={{ left: r - 20, top: r - 20, width: 40, height: 40 }}
      />
      <motion.div
        key={ack} // remount on ack → plays the flash
        className="absolute"
        style={{ left: r - 6, top: r - 6 }}
        initial={reduced ? false : { scale: 1.9, opacity: 0.4 }}
        animate={
          reduced
            ? undefined
            : ack > 0
              ? { scale: [1.9, 1, 1.3, 1], opacity: [0.4, 1, 1, 0.8] }
              : { scale: [1, 1.35, 1], opacity: [0.75, 1, 0.75] }
        }
        transition={
          reduced
            ? undefined
            : ack > 0
              ? { duration: 0.9, ease: 'easeOut' }
              : { duration: 3, repeat: Infinity, ease: 'easeInOut' }
        }
      >
        <span
          className="block h-3 w-3 rounded-full"
          style={{
            background: ack > 0 && !reduced ? '#67e8f9' : '#22d3ee',
            boxShadow: ack > 0 && !reduced
              ? '0 0 26px rgba(103,232,249,1)'
              : '0 0 18px rgba(34,211,238,0.95)',
          }}
        />
      </motion.div>

      {/* mini log ticker (L4) */}
      <div className="absolute left-[14%] right-[14%] bottom-[13%] text-center font-mono text-[9px] leading-[14px]">
        {reduced ? (
          <p className="truncate text-cyan-300/50">{TICKER_POOL[0]}</p>
        ) : (
          <AnimatePresence initial={false}>
            {tickerLines.map((l, i) => (
              <motion.p
                key={l.key}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: [1, 0.55, 0.3][i] ?? 0.3, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.45 }}
                className={i === 0 ? 'truncate text-cyan-300/80' : 'truncate text-content-subtle/50'}
              >
                {l.text}
              </motion.p>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
