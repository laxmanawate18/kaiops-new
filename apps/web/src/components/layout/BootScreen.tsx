import { motion } from 'framer-motion'

/**
 * Full-screen loader shown while the session is being validated or a lazy
 * route chunk is in flight. Deliberately branded — it is the first thing a
 * user sees, and a bare spinner wastes that moment.
 */
export function BootScreen({ label = 'Establishing session' }: { label?: string }) {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center gap-6 bg-canvas">
      <div className="relative flex h-16 w-16 items-center justify-center">
        {/* Concentric sweeps, counter-rotating — reads as instrumentation. */}
        <motion.span
          className="absolute inset-0 rounded-full border border-brand-500/25 border-t-brand-400"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
        />
        <motion.span
          className="absolute inset-2 rounded-full border border-accent/20 border-b-accent/70"
          animate={{ rotate: -360 }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'linear' }}
        />
        <svg viewBox="0 0 32 32" className="relative h-7 w-7" aria-hidden>
          <path
            d="M16 5.5 25 10.5v11L16 26.5 7 21.5v-11L16 5.5Zm0 3.2-6.2 3.45v6.7L16 22.3l6.2-3.45v-6.7L16 8.7Z"
            className="fill-brand-400"
          />
        </svg>
      </div>

      <div className="space-y-1.5 text-center">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-brand-400/80">KaiOPS</p>
        <p className="text-xs text-content-subtle">{label}…</p>
      </div>
    </div>
  )
}
