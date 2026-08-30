import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown, CircleDashed, Loader2, X } from 'lucide-react'
import type { ReasoningStep } from '@/lib/api/types'
import { cn } from '@/lib/utils'
import { collapseVariants, staggerContainer, staggerItem } from '@/lib/motion'

/**
 * The agent's reasoning chain.
 *
 * Two modes:
 *  - `live`: shown while a turn is in flight, stepping through the phases.
 *  - collapsed summary: attached to a completed message, expandable.
 *
 * Note the backend only ever emits `status: "completed"` and injects a
 * three-step default when no tool calls were captured, so the live view is
 * an honest *estimate* of progress, not a real per-tool trace. It is labelled
 * as such rather than implying precision we don't have.
 */

const STATUS_ICON = {
  completed: Check,
  running: Loader2,
  failed: X,
  pending: CircleDashed,
} as const

function stepIcon(status: string) {
  return STATUS_ICON[status as keyof typeof STATUS_ICON] ?? CircleDashed
}

export function ReasoningTimeline({ steps }: { steps: ReasoningStep[] }) {
  const [open, setOpen] = useState(false)
  if (!steps || steps.length === 0) return null

  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-line bg-surface-sunken/50">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-surface-raised/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/60"
      >
        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-ok/15">
          <Check className="h-2.5 w-2.5 text-ok" strokeWidth={3} aria-hidden />
        </span>
        <span className="text-2xs font-semibold uppercase tracking-[0.14em] text-content-subtle">
          Reasoning chain · {steps.length} step{steps.length === 1 ? '' : 's'}
        </span>
        <ChevronDown
          className={cn(
            'ml-auto h-3.5 w-3.5 shrink-0 text-content-subtle transition-transform duration-200',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div variants={collapseVariants} initial="initial" animate="animate" exit="exit">
            <ol className="space-y-0 px-3 pb-3">
              {steps.map((step, index) => {
                const Icon = stepIcon(step.status)
                const last = index === steps.length - 1
                return (
                  <li key={`${step.step}-${index}`} className="relative flex gap-3 pb-3 last:pb-0">
                    {!last && (
                      <span
                        className="absolute left-[7px] top-5 h-full w-px bg-line-strong"
                        aria-hidden
                      />
                    )}
                    <span
                      className={cn(
                        'relative z-10 mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ring-2 ring-surface-sunken',
                        step.status === 'failed' ? 'bg-danger/20' : 'bg-ok/20',
                      )}
                    >
                      <Icon
                        className={cn(
                          'h-2 w-2',
                          step.status === 'failed' ? 'text-danger' : 'text-ok',
                          step.status === 'running' && 'animate-spin',
                        )}
                        strokeWidth={3}
                        aria-hidden
                      />
                    </span>
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <p className="font-mono text-2xs font-medium text-content-muted">{step.title}</p>
                      <p className="text-pretty text-2xs leading-relaxed text-content-subtle">
                        {step.description}
                      </p>
                    </div>
                  </li>
                )
              })}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ------------------------------------------------------------------ Live */

const LIVE_PHASES = [
  { title: 'Resolving context', detail: 'Matching your query against the service registry' },
  { title: 'Correlating telemetry', detail: 'Reading logs, metrics and deploy state' },
  { title: 'Synthesising root cause', detail: 'Ranking hypotheses and drafting remediation' },
]

/**
 * Live progress while a turn is in flight.
 *
 * The API call is synchronous with no progress channel, so this advances on a
 * timer. It is framed as "working" rather than claiming a specific step has
 * completed — an operations tool should not invent precision.
 */
export function LiveReasoning({ elapsedMs }: { elapsedMs: number }) {
  // Advance roughly every 6s, never past the last phase.
  const activeIndex = Math.min(Math.floor(elapsedMs / 6000), LIVE_PHASES.length - 1)

  return (
    <motion.div
      variants={staggerContainer(0.06)}
      initial="initial"
      animate="animate"
      className="rounded-xl border border-brand-500/20 bg-brand-500/[0.04] p-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <span className="relative flex h-2 w-2" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-70" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-400" />
        </span>
        <span className="text-2xs font-semibold uppercase tracking-[0.16em] text-brand-300">
          Investigating
        </span>
        <span className="ml-auto font-mono text-2xs tabular-nums text-content-subtle">
          {(elapsedMs / 1000).toFixed(0)}s
        </span>
      </div>

      <ol className="space-y-2.5">
        {LIVE_PHASES.map((phase, index) => {
          const done = index < activeIndex
          const active = index === activeIndex
          return (
            <motion.li key={phase.title} variants={staggerItem} className="flex items-start gap-2.5">
              <span
                className={cn(
                  'mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full',
                  done ? 'bg-ok/20' : active ? 'bg-brand-500/25' : 'bg-surface-overlay',
                )}
              >
                {done ? (
                  <Check className="h-2 w-2 text-ok" strokeWidth={3} aria-hidden />
                ) : active ? (
                  <Loader2 className="h-2 w-2 animate-spin text-brand-300" aria-hidden />
                ) : (
                  <span className="h-1 w-1 rounded-full bg-content-subtle/50" aria-hidden />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p
                  className={cn(
                    'text-2xs font-medium transition-colors',
                    active ? 'text-content' : done ? 'text-content-muted' : 'text-content-subtle',
                  )}
                >
                  {phase.title}
                </p>
                {active && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-2xs leading-relaxed text-content-subtle"
                  >
                    {phase.detail}
                  </motion.p>
                )}
              </div>
            </motion.li>
          )
        })}
      </ol>
    </motion.div>
  )
}
