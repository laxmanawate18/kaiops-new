import { Suspense, lazy } from 'react'
import { motion } from 'framer-motion'
import { Activity, GitBranch, Radar, ShieldCheck } from 'lucide-react'
import { staggerContainer, staggerItem } from '@/lib/motion'
import { CanvasBoundary } from '@/components/three/CanvasBoundary'

// three.js is ~600kb — it must never be in the critical path. The form is
// fully usable before this chunk resolves.
const AmbientField = lazy(() => import('@/components/three/AmbientField'))

const CAPABILITIES = [
  { icon: Radar, label: 'Multi-cloud RCA', detail: 'GKE, EKS and AKS telemetry correlated in one pass' },
  { icon: GitBranch, label: 'Deploy-aware', detail: 'ArgoCD sync state and the commit that caused it' },
  { icon: Activity, label: 'Grounded', detail: 'Answers cite your service registry, not guesses' },
  { icon: ShieldCheck, label: 'Guarded', detail: 'Destructive actions require explicit human approval' },
]

/**
 * Split auth layout: a branded, animated left panel and a focused form on the
 * right. The panel collapses away under `lg` so the form is never competing
 * with decoration on a small screen.
 */
export function AuthLayout({
  children,
  title,
  subtitle,
}: {
  children: React.ReactNode
  title: string
  subtitle: string
}) {
  return (
    <div className="relative flex min-h-screen w-full bg-canvas">
      {/* ---------------------------------------------------- Brand panel */}
      <div className="relative hidden w-[46%] max-w-2xl flex-col justify-between overflow-hidden border-r border-line p-12 lg:flex">
        {/* Decorative only — if WebGL is unavailable the panel simply keeps
            its gradient wash and the page is unaffected. */}
        <CanvasBoundary>
          <Suspense fallback={null}>
            <AmbientField className="absolute inset-0 opacity-70" density="medium" />
          </Suspense>
        </CanvasBoundary>

        {/* Wash so text keeps contrast over the particle field. */}
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden
          style={{
            background:
              'linear-gradient(160deg, hsl(222 47% 4% / 0.2) 0%, hsl(222 47% 4% / 0.75) 55%, hsl(222 47% 4% / 0.95) 100%)',
          }}
        />

        <motion.div
          variants={staggerContainer(0.08)}
          initial="initial"
          animate="animate"
          className="relative z-10"
        >
          <motion.div variants={staggerItem} className="flex items-center gap-3">
            <svg viewBox="0 0 32 32" className="h-9 w-9" aria-hidden>
              <rect width="32" height="32" rx="8" className="fill-surface-overlay" />
              <path
                d="M16 5.5 25 10.5v11L16 26.5 7 21.5v-11L16 5.5Zm0 3.2-6.2 3.45v6.7L16 22.3l6.2-3.45v-6.7L16 8.7Z"
                className="fill-brand-400"
              />
              <path d="M16 12.4 20 14.6 16 16.8 12 14.6 16 12.4Z" className="fill-brand-200" />
            </svg>
            <div className="leading-tight">
              <p className="text-lg font-bold tracking-[0.16em] text-content">KaiOPS</p>
              <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-brand-400">
                Incidents End Here
              </p>
            </div>
          </motion.div>
        </motion.div>

        <motion.div
          variants={staggerContainer(0.07, 0.15)}
          initial="initial"
          animate="animate"
          className="relative z-10 space-y-10"
        >
          <motion.h1
            variants={staggerItem}
            className="max-w-md text-balance text-4xl font-bold leading-[1.12] tracking-tight text-content"
          >
            Your on-call engineer that already read{' '}
            <span className="bg-gradient-to-r from-brand-300 to-accent bg-clip-text text-transparent">
              every log
            </span>
            .
          </motion.h1>

          <motion.div variants={staggerContainer(0.05)} className="grid gap-4 sm:grid-cols-2">
            {CAPABILITIES.map(({ icon: Icon, label, detail }) => (
              <motion.div key={label} variants={staggerItem} className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 shrink-0 text-brand-400" aria-hidden />
                  <p className="text-xs font-semibold text-content">{label}</p>
                </div>
                <p className="text-pretty text-xs leading-relaxed text-content-subtle">{detail}</p>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>

        <motion.p
          variants={staggerItem}
          initial="initial"
          animate="animate"
          className="relative z-10 font-mono text-2xs text-content-subtle/70"
        >
          Autonomous SRE · Multi-cloud RCA · Human-in-the-loop remediation
        </motion.p>
      </div>

      {/* ----------------------------------------------------------- Form */}
      <div className="relative flex flex-1 items-center justify-center px-5 py-10">
        <div className="absolute inset-0 bg-grid opacity-[0.35] lg:hidden" aria-hidden />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-full max-w-sm"
        >
          {/* Compact brand mark for the small-screen layout. */}
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
              <rect width="32" height="32" rx="8" className="fill-surface-overlay" />
              <path
                d="M16 5.5 25 10.5v11L16 26.5 7 21.5v-11L16 5.5Zm0 3.2-6.2 3.45v6.7L16 22.3l6.2-3.45v-6.7L16 8.7Z"
                className="fill-brand-400"
              />
            </svg>
            <p className="text-base font-bold tracking-[0.16em] text-content">KaiOPS</p>
          </div>

          <div className="mb-7 space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-content">{title}</h2>
            <p className="text-sm leading-relaxed text-content-muted">{subtitle}</p>
          </div>

          {children}
        </motion.div>
      </div>
    </div>
  )
}
