import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, Bot, Check, Copy, ThumbsDown, ThumbsUp, User } from 'lucide-react'
import { toast } from 'sonner'
import type { ChatMessage, MessageMetadata } from '@/lib/api/types'
import { cn, formatRelative } from '@/lib/utils'
import { messageVariants } from '@/lib/motion'
import { Markdown } from './Markdown'
import { ReasoningTimeline } from './ReasoningTimeline'
import { ApprovalCard } from './ApprovalCard'
import { SeverityBadge, type Severity } from '@/components/ui/Badge'
import { Tooltip } from '@/components/ui/primitives'

interface MessageBubbleProps {
  message: ChatMessage
  /** The user turn this reply answers — needed for meaningful feedback. */
  precedingUserText?: string
  onFeedback?: (message: ChatMessage, kind: 'up' | 'down', userText: string) => void
  onApprovalDecision?: (decision: 'approve' | 'reject', token: string) => void
  busy?: boolean
  approvalPending?: boolean
  /** Persisted vote for this message (from feedbackApi.mine), survives reloads. */
  initialVote?: 'up' | 'down' | null
}

function isErrorMessage(meta: MessageMetadata | null | undefined, text: string): boolean {
  // The agent-failure path sets metadata to exactly {error: "..."} with no
  // reasoning_steps, so that key is the reliable signal — not string sniffing.
  if (meta && typeof meta.error === 'string') return true
  return /^(error|an error occurred)/i.test(text.trim())
}

export function MessageBubble({
  message,
  precedingUserText,
  onFeedback,
  onApprovalDecision,
  busy,
  approvalPending,
  initialVote,
}: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  // Seeded from the user's persisted feedback (feedbackApi.mine) so votes
  // survive reloads instead of living only in component state.
  const [voted, setVoted] = useState<'up' | 'down' | null>(initialVote ?? null)

  useEffect(() => {
    setVoted(initialVote ?? null)
  }, [initialVote])

  const isUser = message.sender === 'user'
  const meta = message.metadata ?? undefined
  const text = message.text ?? ''
  const errored = !isUser && isErrorMessage(meta, text)

  // These metadata keys are ABSENT rather than false when not applicable.
  // A card without an approval_token is a legacy message — the endpoints need
  // the token, so rendering a dead card would just mislead the operator.
  const needsApproval = Boolean(
    meta && meta.requires_confirmation && typeof meta.approval_token === 'string' && meta.approval_token,
  )
  const severity = typeof meta?.severity === 'string' ? (meta.severity as Severity) : null
  const steps = Array.isArray(meta?.reasoning_steps) ? meta.reasoning_steps : []

  // A3: domain chips — which systems the agent actually touched this turn.
  const TOOL_DOMAINS: Record<string, { label: string; color: string }> = {
    get_application_status: { label: 'ArgoCD', color: '#8b5cf6' },
    sync_application: { label: 'ArgoCD', color: '#8b5cf6' },
    rollback_application: { label: 'ArgoCD', color: '#8b5cf6' },
    get_deployment_history: { label: 'ArgoCD', color: '#8b5cf6' },
    search_applications: { label: 'ArgoCD', color: '#8b5cf6' },
    list_repositories: { label: 'ArgoCD', color: '#8b5cf6' },
    list_projects: { label: 'ArgoCD', color: '#8b5cf6' },
    search_dashboards: { label: 'Grafana', color: '#06b6d4' },
    get_dashboard_summary: { label: 'Grafana', color: '#06b6d4' },
    list_alert_rules: { label: 'Grafana', color: '#06b6d4' },
    query_prometheus: { label: 'Prometheus', color: '#06b6d4' },
    query_loki: { label: 'Loki', color: '#06b6d4' },
    restart_pod: { label: 'Kubernetes', color: '#22c55e' },
    check_application_logs: { label: 'Cloud Logs', color: '#f59e0b' },
    check_ingress_logs: { label: 'Cloud Logs', color: '#f59e0b' },
    analyze_pod_logs: { label: 'Cloud Logs', color: '#f59e0b' },
    search_repositories: { label: 'GitHub', color: '#ec4899' },
    get_latest_commit: { label: 'GitHub', color: '#ec4899' },
    get_repository_info: { label: 'GitHub', color: '#ec4899' },
    search_code: { label: 'GitHub', color: '#ec4899' },
    list_issues: { label: 'GitHub', color: '#ec4899' },
    get_user_repositories: { label: 'GitHub', color: '#ec4899' },
    search_application_by_name: { label: 'Registry', color: '#4285F4' },
    list_all_applications: { label: 'Registry', color: '#4285F4' },
    query_mongodb: { label: 'Registry', color: '#4285F4' },
    search_runbooks: { label: 'Runbooks', color: '#14b8a6' },
    search_past_incidents: { label: 'Memory', color: '#94a3b8' },
    search_approved_feedback: { label: 'Memory', color: '#94a3b8' },
  }
  const toolChips = (() => {
    if (isUser || steps.length === 0) return []
    const seen = new Set<string>()
    for (const s of steps) {
      const m = /Invoking (\w+)/.exec(s.title || '')
      const domain = m ? TOOL_DOMAINS[m[1]] : undefined
      if (domain) seen.add(`${domain.label}|${domain.color}`)
    }
    return [...seen].map((v) => {
      const [label, color] = v.split('|')
      return { label, color }
    })
  })()

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      toast.error('Could not copy', { description: 'Your browser blocked clipboard access.' })
    }
  }

  const vote = (kind: 'up' | 'down') => {
    if (voted || !onFeedback) return
    setVoted(kind)
    onFeedback(message, kind, precedingUserText || 'User query')
  }

  return (
    <motion.div
      variants={messageVariants(isUser)}
      initial="initial"
      animate="animate"
      className={cn('group flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      {/* Avatar */}
      <div
        className={cn(
          'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ring-1',
          isUser
            ? 'bg-brand-500/15 ring-brand-500/25'
            : errored
              ? 'bg-danger/12 ring-danger/25'
              : 'bg-accent/12 ring-accent/25',
        )}
        aria-hidden
      >
        {isUser ? (
          <User className="h-3.5 w-3.5 text-brand-300" />
        ) : errored ? (
          <AlertTriangle className="h-3.5 w-3.5 text-danger" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-accent" />
        )}
      </div>

      <div className={cn('flex min-w-0 max-w-[min(46rem,85%)] flex-col', isUser && 'items-end')}>
        {/* Meta line */}
        <div className={cn('mb-1 flex items-center gap-2', isUser && 'flex-row-reverse')}>
          <span className="text-2xs font-medium text-content-muted">
            {isUser ? 'You' : 'KaiOPS'}
          </span>
          <span className="font-mono text-[10px] text-content-subtle">
            {formatRelative(message.timestamp)}
          </span>
          {severity && <SeverityBadge severity={severity} pulse />}
        </div>

        {/* Body */}
        <div
          className={cn(
            'w-full rounded-2xl border px-4 py-3',
            isUser
              ? 'rounded-tr-sm border-brand-500/25 bg-brand-500/10'
              : errored
                ? 'rounded-tl-sm border-danger/25 bg-danger/[0.05]'
                : 'rounded-tl-sm border-line bg-surface/70',
          )}
        >
          {!isUser && toolChips.length > 0 && (
            <div className="mb-1.5 flex flex-wrap items-center gap-1">
              {toolChips.map((c) => (
                <span
                  key={c.label}
                  className="inline-flex items-center gap-1 rounded border border-line-strong bg-surface-overlay px-1.5 py-[2px] text-[10px] text-content-muted"
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: c.color }} aria-hidden />
                  {c.label}
                </span>
              ))}
            </div>
          )}

          {!isUser && steps.length > 0 && <ReasoningTimeline steps={steps} />}

          {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-content">{text}</p>
          ) : (
            <Markdown>{text}</Markdown>
          )}

          {needsApproval && meta && onApprovalDecision && (
            <ApprovalCard
              metadata={meta}
              onDecision={onApprovalDecision}
              disabled={busy || approvalPending}
            />
          )}
        </div>

        {/* Actions — assistant only, revealed on hover/focus */}
        {!isUser && (
          <div
            className={cn(
              'mt-1.5 flex items-center gap-1 opacity-0 transition-opacity duration-150',
              'group-hover:opacity-100 focus-within:opacity-100',
            )}
          >
            <Tooltip content={copied ? 'Copied' : 'Copy response'}>
              <button
                type="button"
                onClick={copy}
                className="rounded-md p-1.5 text-content-subtle transition-colors hover:bg-surface-raised hover:text-content focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                aria-label={copied ? 'Copied' : 'Copy response'}
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-ok" aria-hidden />
                ) : (
                  <Copy className="h-3.5 w-3.5" aria-hidden />
                )}
              </button>
            </Tooltip>

            {onFeedback && !errored && (
              <>
                <Tooltip content={voted === 'down' ? 'Already rated' : 'Helpful'}>
                  <button
                    type="button"
                    onClick={() => vote('up')}
                    disabled={voted !== null}
                    aria-label="Mark as helpful"
                    aria-pressed={voted === 'up'}
                    className={cn(
                      'rounded-md p-1.5 transition-colors focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                      voted === 'up'
                        ? 'bg-ok/15 text-ok'
                        : 'text-content-subtle hover:bg-surface-raised hover:text-ok',
                      voted === 'down' && 'opacity-30',
                    )}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </Tooltip>

                <Tooltip content={voted === 'up' ? 'Already rated' : 'Not helpful'}>
                  <button
                    type="button"
                    onClick={() => vote('down')}
                    disabled={voted !== null}
                    aria-label="Mark as not helpful"
                    aria-pressed={voted === 'down'}
                    className={cn(
                      'rounded-md p-1.5 transition-colors focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                      voted === 'down'
                        ? 'bg-danger/15 text-danger'
                        : 'text-content-subtle hover:bg-surface-raised hover:text-danger',
                      voted === 'up' && 'opacity-30',
                    )}
                  >
                    <ThumbsDown className="h-3.5 w-3.5" aria-hidden />
                  </button>
                </Tooltip>
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
}
