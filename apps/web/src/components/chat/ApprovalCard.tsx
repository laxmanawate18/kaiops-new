import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, ShieldAlert, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/Dialog'
import type { MessageMetadata } from '@/lib/api/types'

/**
 * Human-in-the-loop gate for a guarded tool call.
 *
 * The backend exposes single-use approve/reject endpoints keyed by an
 * `approval_token` carried in message metadata. Approving or declining hits
 * those endpoints directly — no conversational follow-up turn is sent.
 */
export function ApprovalCard({
  metadata,
  onDecision,
  disabled,
}: {
  metadata: MessageMetadata
  onDecision: (decision: 'approve' | 'reject', token: string) => void
  disabled?: boolean
}) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [resolved, setResolved] = useState<'approve' | 'reject' | null>(null)

  const tool = metadata.pending_tool || 'unknown_tool'
  const policy = metadata.model_armor?.policy || 'DESTRUCTIVE_ACTION_PROTECTION'
  const token = metadata.approval_token ?? ''

  const decide = (decision: 'approve' | 'reject') => {
    setResolved(decision)
    setConfirmOpen(false)
    if (token) onDecision(decision, token)
  }

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        className="my-3 overflow-hidden rounded-xl border border-warn/35 bg-warn/[0.06]"
        role="region"
        aria-label="Action requires approval"
      >
        <div className="flex items-center gap-2.5 border-b border-warn/20 bg-warn/[0.06] px-4 py-2.5">
          <ShieldAlert className="h-4 w-4 shrink-0 text-warn" aria-hidden />
          <span className="text-2xs font-semibold uppercase tracking-[0.14em] text-warn">
            Approval required
          </span>
          <span className="ml-auto rounded border border-warn/30 bg-warn/10 px-1.5 py-0.5 font-mono text-[10px] text-warn/90">
            {policy}
          </span>
        </div>

        <div className="space-y-3 p-4">
          <p className="text-sm leading-relaxed text-content-muted">
            The agent wants to run a guarded tool:{' '}
            <code className="rounded border border-warn/30 bg-surface-sunken px-1.5 py-0.5 font-mono text-xs text-warn">
              {tool}
            </code>
          </p>

          {resolved === null ? (
            <>
              <p className="text-2xs leading-relaxed text-content-subtle">
                Approving executes the pending tool via the approval endpoint. Review the reasoning
                above before deciding — you are accountable for what runs.
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-0.5">
                <Button
                  variant="primary"
                  size="sm"
                  disabled={disabled}
                  onClick={() => setConfirmOpen(true)}
                >
                  <Check className="h-3.5 w-3.5" aria-hidden />
                  Approve and continue
                </Button>
                <Button variant="ghost" size="sm" disabled={disabled} onClick={() => decide('reject')}>
                  <X className="h-3.5 w-3.5" aria-hidden />
                  Decline
                </Button>
              </div>
            </>
          ) : (
            <div
              className={
                resolved === 'approve'
                  ? 'flex items-center gap-2 rounded-lg border border-ok/25 bg-ok/10 px-3 py-2 text-xs text-ok'
                  : 'flex items-center gap-2 rounded-lg border border-line-strong bg-surface-raised px-3 py-2 text-xs text-content-muted'
              }
            >
              {resolved === 'approve' ? (
                <Check className="h-3.5 w-3.5 shrink-0" aria-hidden />
              ) : (
                <X className="h-3.5 w-3.5 shrink-0" aria-hidden />
              )}
              {resolved === 'approve'
                ? 'Approved — the action was executed. See the next messages for the outcome.'
                : 'Declined. The agent was told not to proceed.'}
            </div>
          )}
        </div>
      </motion.div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        onConfirm={() => decide('approve')}
        tone="warning"
        title={`Approve ${tool}?`}
        description={
          <>
            This authorises the agent to proceed with a potentially destructive operation against your
            infrastructure. Make sure the diagnosis above is sound before approving.
          </>
        }
        confirmText="Yes, approve"
        cancelText="Go back"
      />
    </>
  )
}
