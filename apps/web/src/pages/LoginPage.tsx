import { Suspense, lazy, useState, useRef, useEffect } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AnimatePresence, motion, useMotionValue, useSpring } from 'framer-motion'
import { AlertCircle, ArrowRight, Eye, EyeOff, Zap } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { TextField } from '@/components/ui/Input'
import { useAuth } from '@/lib/auth/AuthProvider'
import { ApiError } from '@/lib/api/client'
import { BootScreen } from '@/components/layout/BootScreen'
import { CanvasBoundary } from '@/components/three/CanvasBoundary'
import HeroCore from '@/components/login/HeroCore'
import { CountUp } from '@/components/ui/CountUp'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { cn } from '@/lib/utils'

const HeroParticles = lazy(() => import('@/components/three/HeroParticles'))

const schema = z.object({
  username: z.string().min(1, 'Enter your username'),
  password: z.string().min(1, 'Enter your password'),
})
type FormValues = z.infer<typeof schema>

// ── Magnetic button wrapper ───────────────────────────────────────────────────
function Magnetic({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 300, damping: 20 })
  const sy = useSpring(y, { stiffness: 300, damping: 20 })

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    x.set((e.clientX - r.left - r.width / 2) * 0.3)
    y.set((e.clientY - r.top - r.height / 2) * 0.3)
  }
  const reset = () => { x.set(0); y.set(0) }

  return (
    <div ref={ref} onMouseMove={onMove} onMouseLeave={reset} className="inline-block">
      <motion.div style={{ x: sx, y: sy }}>{children}</motion.div>
    </div>
  )
}

export default function LoginPage() {
  const { login, isAuthenticated, initializing } = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()
  const [formError, setFormError] = useState<string | null>(null)
  const [showPass, setShowPass]   = useState(false)
  const [morphed, setMorphed]     = useState(false)

  const reducedMotion = usePrefersReducedMotion()

  // ── Rotating typewriter taglines (L3) ──
  const PHRASES = ['that never sleeps.', 'that triages at 3 AM.', 'that closes the loop.']
  const LONGEST_PHRASE = PHRASES.reduce((a, b) => (b.length > a.length ? b : a))
  const [phraseIdx, setPhraseIdx] = useState(0)
  const [count, setCount] = useState(reducedMotion ? PHRASES[0].length : 0)
  const [mode, setMode] = useState<'type' | 'hold' | 'del'>('type')
  // Sticky: the feature-row cascade fires once, after the first phrase types out.
  const [introDone, setIntroDone] = useState(reducedMotion)
  const typingDone = introDone

  useEffect(() => {
    const t = setTimeout(() => setMorphed(true), 600)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    if (reducedMotion) { setCount(PHRASES[0].length); setIntroDone(true); return }
    const phrase = PHRASES[phraseIdx]
    let t: ReturnType<typeof setTimeout>
    if (mode === 'type') {
      if (count < phrase.length) {
        t = setTimeout(() => setCount((c) => c + 1), 42)
      } else {
        if (phraseIdx === 0) setIntroDone(true)
        t = setTimeout(() => setMode('hold'), 2600)
      }
    } else if (mode === 'hold') {
      t = setTimeout(() => setMode('del'), 300)
    } else {
      if (count > 0) {
        t = setTimeout(() => setCount((c) => c - 1), 20)
      } else {
        setPhraseIdx((i) => (i + 1) % PHRASES.length)
        setMode('type')
      }
    }
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, count, reducedMotion])

  const typedText = PHRASES[phraseIdx].slice(0, count)

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } =
    useForm<FormValues>({ resolver: zodResolver(schema) })

  if (initializing)    return <BootScreen />
  if (isAuthenticated) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from || '/console'} replace />
  }

  const onSubmit = handleSubmit(async (values) => {
    // Deterministic visible feedback even if field-level rendering hiccups.
    if (!values.username.trim() || !values.password.trim()) {
      setFormError('Enter your username and password to continue.')
      return
    }
    setFormError(null)
    try {
      await login(values)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from || '/console', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        Object.entries(err.fieldErrors).forEach(([f, m]) => {
          if (f === 'username' || f === 'password') setError(f, { message: m })
        })
        setFormError(err.status === 401 ? 'That username and password combination did not work.' : err.message)
      } else {
        setFormError('Something went wrong signing you in.')
      }
    }
  })

  return (
    <div className="relative flex min-h-screen w-full overflow-hidden bg-[#05070d]">

      {/* ── Full-screen 3D particle canvas ── */}
      <CanvasBoundary>
        <Suspense fallback={null}>
          <HeroParticles
            className="pointer-events-none absolute inset-0 z-0"
            morphed={morphed}
            count={2400}
          />
        </Suspense>
      </CanvasBoundary>

      {/* ── Gradient washes ── */}
      <div className="pointer-events-none absolute inset-0 z-10"
        style={{ background: 'radial-gradient(ellipse 60% 60% at 30% 50%, rgba(6,182,212,0.07) 0%, transparent 70%)' }} />
      <div className="pointer-events-none absolute inset-0 z-10"
        style={{ background: 'radial-gradient(ellipse 40% 40% at 70% 50%, rgba(139,92,246,0.06) 0%, transparent 70%)' }} />

      {/* ── Subtle grid ── */}
      <div className="pointer-events-none absolute inset-0 z-10 opacity-[0.03]"
        style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
        }} />

      {/* ── Animated core inside the hexagon ── */}
      <HeroCore />

      {/* ── Left: Brand panel ── */}
      <motion.div
        className="relative z-20 hidden w-[52%] flex-col justify-between p-16 lg:flex"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.2, ease: 'easeOut' }}
      >
        {/* Logo */}
        <motion.div
          className="flex items-center gap-3"
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-500/20 bg-cyan-500/10 shadow-[0_0_20px_rgba(6,182,212,0.2)]">
            <svg viewBox="0 0 32 32" className="h-7 w-7">
              <path d="M16 4 27 10v12L16 28 5 22V10L16 4Zm0 2.8-8.7 4.9v9.6L16 26.2l8.7-4.9v-9.6L16 6.8Z" fill="rgb(6 182 212)" />
              <path d="M16 11.5 21 14.3 16 17l-5-2.7 5-2.8Z" fill="rgb(165 243 252)" />
            </svg>
          </div>
          <div>
            <p className="text-xl font-bold tracking-[0.18em] text-white">KaiOPS</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-cyan-400/80">SRE AI Agent</p>
          </div>
        </motion.div>

        {/* Hero copy */}
        <div className="space-y-8">
          <motion.h1
            className="max-w-lg text-[3.2rem] font-bold leading-[1.08] tracking-tight text-white"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.5, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          >
            Your on-call engineer{' '}
            {/* gradient classes live on the TEXT spans — bg-clip-text on a
                grid ancestor silently fails to paint children glyphs.
                Sizer uses the longest rotating phrase → zero layout shift. */}
            <span className="grid">
              <span
                aria-hidden
                className="col-start-1 row-start-1 invisible bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent"
              >
                {LONGEST_PHRASE}
              </span>
              <span
                aria-hidden={mode === 'del'}
                className="col-start-1 row-start-1 bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent"
              >
                {typedText}
                <span
                  className={cn(
                    'ml-0.5 inline-block h-[0.95em] w-[3px] translate-y-[0.12em] bg-cyan-300',
                    mode !== 'del' ? 'animate-pulse' : '',
                  )}
                />
              </span>
              <span className="sr-only">that never sleeps.</span>
            </span>
          </motion.h1>

          {/* Feature rows cascade in one-by-one after the tagline types out */}
          <motion.div
            className="space-y-4"
            initial="hidden"
            animate={typingDone ? 'show' : 'hidden'}
            variants={{
              hidden: {},
              show: { transition: { staggerChildren: reducedMotion ? 0 : 0.38, delayChildren: reducedMotion ? 0 : 0.05 } },
            }}
          >
            {[
              { label: 'Multi-cloud RCA', detail: 'GKE, EKS, AKS telemetry — correlated in one pass' },
              { label: 'Deploy-aware',    detail: 'ArgoCD sync state + the commit that caused it' },
              { label: 'Human-in-loop',  detail: 'Destructive actions require your explicit approval' },
            ].map(({ label, detail }) => (
              <motion.div
                key={label}
                className="flex items-center gap-3 group"
                variants={{
                  hidden: { opacity: 0, x: -26 },
                  show: { opacity: 1, x: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
                }}
              >
                <div className="h-px w-8 bg-gradient-to-r from-cyan-500/60 to-transparent transition-all duration-300 group-hover:w-12" />
                <span className="text-sm font-semibold text-white/90">{label}</span>
                <span className="text-xs text-white/40">{detail}</span>
              </motion.div>
            ))}
          </motion.div>

          {/* Live status pill — count-up ticker (L5) */}
          <motion.div
            className="inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/5 px-4 py-2 text-xs text-cyan-300/80 backdrop-blur-sm"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: reducedMotion ? 0.5 : 2.15, duration: 0.5 }}
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
            </span>
            All systems operational ·&nbsp;
            <span className="font-semibold text-cyan-200">
              <CountUp to={128} active={introDone} />
            </span>
            &nbsp;incidents auto-resolved this week
          </motion.div>
        </div>

        <motion.p
          className="font-mono text-[11px] text-white/20"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: reducedMotion ? 0.6 : 2.35 }}
        >
          Autonomous SRE · Multi-cloud · Human-in-the-loop
        </motion.p>
      </motion.div>

      {/* ── Right: Glass form panel ── */}
      <div className="relative z-20 flex flex-1 items-center justify-center px-6 py-10">
        <motion.div
          className="w-full max-w-[400px]"
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ delay: 0.4, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        >
          {/* Glass card — scanline sweep on focus (L6) + corner brackets */}
          <div className="login-card relative overflow-hidden rounded-2xl border border-white/[0.08] bg-white/[0.04] p-8 shadow-2xl backdrop-blur-2xl">
            <style>{`
              .login-card .card-scanline { opacity: 0 }
              .login-card:focus-within .card-scanline {
                animation: cardScan 2.4s linear infinite
              }
              @keyframes cardScan {
                0% { top: -2%; opacity: 0 }
                10% { opacity: .55 }
                90% { opacity: .55 }
                100% { top: 102%; opacity: 0 }
              }
              @media (prefers-reduced-motion: reduce) {
                .login-card:focus-within .card-scanline { animation: none }
              }
            `}</style>
            {/* corner brackets */}
            <span aria-hidden className="pointer-events-none absolute left-2 top-2 h-4 w-4 border-l border-t border-cyan-400/40" />
            <span aria-hidden className="pointer-events-none absolute right-2 top-2 h-4 w-4 border-r border-t border-cyan-400/40" />
            <span aria-hidden className="pointer-events-none absolute bottom-2 left-2 h-4 w-4 border-b border-l border-cyan-400/40" />
            <span aria-hidden className="pointer-events-none absolute bottom-2 right-2 h-4 w-4 border-b border-r border-cyan-400/40" />
            {/* scanline */}
            <span aria-hidden className="card-scanline pointer-events-none absolute left-3 right-3 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
            {/* Inner glow */}
            <div className="pointer-events-none absolute inset-0 rounded-2xl"
              style={{ background: 'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(6,182,212,0.08), transparent)' }} />

            {/* Mobile brand */}
            <div className="mb-8 flex items-center gap-2.5 lg:hidden">
              <svg viewBox="0 0 32 32" className="h-7 w-7">
                <path d="M16 4 27 10v12L16 28 5 22V10L16 4Zm0 2.8-8.7 4.9v9.6L16 26.2l8.7-4.9v-9.6L16 6.8Z" fill="rgb(6 182 212)" />
              </svg>
              <p className="text-base font-bold tracking-[0.18em] text-white">KaiOPS</p>
            </div>

            <div className="relative mb-7 space-y-1.5">
              <h2 className="text-2xl font-semibold tracking-tight text-white">Sign in</h2>
              <p className="text-sm text-white/40">Access the incident console.</p>
            </div>

            <form onSubmit={onSubmit} className="relative space-y-5" noValidate>
              <AnimatePresence mode="wait">
                {formError && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="flex items-start gap-2.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3.5 py-3 text-sm text-red-400">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      {formError}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <TextField
                label="Username"
                autoComplete="username"
                autoFocus
                placeholder="your.username"
                error={errors.username?.message}
                {...register('username')}
              />

              <TextField
                label="Password"
                type={showPass ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="••••••••••"
                error={errors.password?.message}
                trailingSlot={
                  <button
                    type="button"
                    onClick={() => setShowPass(v => !v)}
                    aria-label={showPass ? 'Hide password' : 'Show password'}
                    className="rounded p-1.5 text-white/30 transition-colors hover:text-white/70"
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
                {...register('password')}
              />

              <Magnetic>
                <Button type="submit" variant="primary" size="lg" loading={isSubmitting} className="w-full">
                  {isSubmitting ? 'Verifying' : 'Enter console'}
                  {!isSubmitting && <ArrowRight className="h-4 w-4" />}
                </Button>
              </Magnetic>
            </form>

            <p className="relative mt-6 text-center text-xs text-white/30">
              Need an account?{' '}
              <Link to="/register" className="font-medium text-cyan-400/80 transition-colors hover:text-cyan-300">
                Register here
              </Link>
            </p>
          </div>

          {/* Incident simulate hint */}
          <motion.div
            className="mt-4 flex items-center justify-center gap-2 text-[11px] text-white/20"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.1 }}
          >
            <Zap className="h-3 w-3 text-cyan-500/40" />
            P0 incident detection is always active
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}
