import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Inbox, ThumbsDown, ThumbsUp, X } from 'lucide-react'
import { toast } from 'sonner'
import { feedbackApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { ApiError } from '@/lib/api/client'
import { FEEDBACK_CATEGORY_LABELS, type Feedback, type FeedbackCategoryValue } from '@/lib/api/types'
import { GlowCard, CardBody, SectionLabel, Tabs, TabsList, TabsTrigger } from '@/components/ui/primitives'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Markdown } from '@/components/chat/Markdown'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn, formatRelative } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'

/* ── Queue item with perspective tilt + cursor glow ──────────────────── */
function QueueItem({
  item,
  isSelected,
  onSelect,
}: {
  item: Feedback
  isSelected: boolean
  onSelect: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [glow, setGlow] = useState({ x: 50, y: 50, show: false })
  const positive = item.feedback_type === 'THUMBS_UP'
  const accent = positive ? '#22c55e' : '#ef4444'

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    setTilt({ x: (py - 0.5) * -5, y: (px - 0.5) * 5 })
    setGlow({ x: px * 100, y: py * 100, show: true })
  }
  const reset = () => { setTilt({ x: 0, y: 0 }); setGlow(g => ({ ...g, show: false })) }

  return (
    <motion.li variants={staggerItem} className="mb-2">
      <button
        ref={ref}
        type="button"
        onClick={onSelect}
        onMouseMove={onMove}
        onMouseLeave={reset}
        aria-current={isSelected}
        style={{
          transform: `perspective(600px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
          transition: 'transform 0.12s ease-out',
        }}
        className={cn(
          'relative w-full overflow-hidden rounded-lg border p-3 text-left',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
          isSelected
            ? 'border-brand-500/40 bg-brand-500/[0.07]'
            : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.10]',
        )}
      >
        {/* Cursor glow */}
        <span
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 h-24 w-24 rounded-full transition-opacity duration-300"
          style={{
            left: `${glow.x}%`,
            top: `${glow.y}%`,
            background: `radial-gradient(circle, ${accent}18, transparent 70%)`,
            opacity: glow.show && !isSelected ? 1 : 0,
          }}
          aria-hidden
        />
        <div className="relative mb-2 flex items-center gap-2">
          <span
            className={cn(
              'flex h-5 w-5 shrink-0 items-center justify-center rounded',
              positive ? 'bg-ok/15 text-ok' : 'bg-danger/15 text-danger',
            )}
            aria-hidden
          >
            {positive ? <ThumbsUp className="h-3 w-3" /> : <ThumbsDown className="h-3 w-3" />}
          </span>
          <span className="relative truncate text-xs font-medium text-content">
            {item.username || 'Unknown'}
          </span>
          <span className="relative ml-auto shrink-0 font-mono text-[10px] text-content-subtle">
            {formatRelative(item.created_at)}
          </span>
        </div>

        <p className="relative line-clamp-2 text-2xs leading-relaxed text-content-muted">
          {item.user_message || 'No question captured'}
        </p>

        {item.tags && item.tags.length > 0 && (
          <ul className="relative mt-2 flex flex-wrap gap-1">
            {item.tags.slice(0, 3).map((tag) => (
              <li key={tag}>
                <Badge tone="neutral" size="sm">
                  {FEEDBACK_CATEGORY_LABELS[tag as FeedbackCategoryValue] ?? tag}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </button>
    </motion.li>
  )
}

export default function FeedbackPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'pending' | 'mine'>('pending')
  const [selected, setSelected] = useState<Feedback | null>(null)
  const [reviewNote, setReviewNote] = useState('')

  const pendingQuery = useQuery({
    queryKey: qk.feedbackPending,
    queryFn: () => feedbackApi.pending(100),
    enabled: tab === 'pending',
  })

  const mineQuery = useQuery({
    queryKey: qk.feedbackMine,
    queryFn: () => feedbackApi.mine(100),
    enabled: tab === 'mine',
  })

  const active = tab === 'pending' ? pendingQuery : mineQuery
  const items = useMemo(() => active.data ?? [], [active.data])

  const review = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'APPROVED' | 'DENIED' }) =>
      feedbackApi.review(id, { status, reviewer_comment: reviewNote || undefined }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.feedbackPending })
      queryClient.invalidateQueries({ queryKey: qk.feedbackStats })
      toast.success(variables.status === 'APPROVED' ? 'Approved' : 'Declined', {
        description: 'Removed from the queue.',
      })
      setSelected(null)
      setReviewNote('')
    },
    onError: (error: ApiError) => toast.error('Review failed', { description: error.message }),
  })

  return (
    <div className="flex h-full">
      {/* Queue */}
      <div className="flex w-full max-w-md shrink-0 flex-col border-r border-white/[0.06]">
        <div className="shrink-0 space-y-3 border-b border-white/[0.06] bg-white/[0.02] p-5 backdrop-blur-sm">
          <div className="space-y-1">
            <SectionLabel className="text-brand-400">Quality</SectionLabel>
            <h1 className="text-lg font-semibold tracking-tight text-content">Review queue</h1>
            <p className="text-2xs text-content-subtle">
              Approved feedback becomes training data for the agent.
            </p>
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
            <TabsList>
              <TabsTrigger value="pending">Awaiting review</TabsTrigger>
              <TabsTrigger value="mine">Mine</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          {active.isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full rounded-lg" />
              ))}
            </div>
          ) : active.isError ? (
            <ErrorState
              title="Could not load the queue"
              message={(active.error as ApiError)?.message}
              onRetry={() => active.refetch()}
            />
          ) : items.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title={tab === 'pending' ? 'Queue is clear' : 'No feedback yet'}
              description={
                tab === 'pending'
                  ? 'Nothing is waiting on review right now.'
                  : 'Rate answers in the console and they will show up here.'
              }
            />
          ) : (
            <motion.ul variants={staggerContainer(0.03)} initial="initial" animate="animate" className="p-3">
              {items.map((item) => (
                <QueueItem
                  key={item.id}
                  item={item}
                  isSelected={selected?.id === item.id}
                  onSelect={() => { setSelected(item); setReviewNote('') }}
                />
              ))}
            </motion.ul>
          )}
        </div>
      </div>

      {/* Detail */}
      <div className="min-w-0 flex-1 overflow-y-auto scrollbar-thin">
        <AnimatePresence mode="wait">
          {!selected ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex h-full items-center justify-center"
            >
              <EmptyState
                icon={Inbox}
                title="Select an item to review"
                description="Pick something from the queue to see the full exchange."
              />
            </motion.div>
          ) : (
            <motion.div
              key={selected.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mx-auto max-w-3xl space-y-5 p-6"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={selected.feedback_type === 'THUMBS_UP' ? 'ok' : 'danger'} dot>
                  {selected.feedback_type === 'THUMBS_UP' ? 'Helpful' : 'Not helpful'}
                </Badge>
                <Badge tone={selected.status === 'PENDING' ? 'warn' : 'neutral'}>
                  {selected.status}
                </Badge>
                {selected.rating != null && (
                  <Badge tone="neutral">Rated {selected.rating}/5</Badge>
                )}
                <span className="ml-auto font-mono text-2xs text-content-subtle">
                  {formatRelative(selected.created_at)}
                </span>
              </div>

              <GlowCard accent="#06b6d4">
                <CardBody className="space-y-4 pt-5">
                  <div className="space-y-1.5">
                    <SectionLabel>Question asked</SectionLabel>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-content">
                      {selected.user_message || '—'}
                    </p>
                  </div>

                  <div className="rule-fade" />

                  <div className="space-y-1.5">
                    <SectionLabel>Agent answer</SectionLabel>
                    <div className="max-h-80 overflow-y-auto scrollbar-thin rounded-lg border border-white/[0.06] bg-surface-sunken/50 p-3">
                      <Markdown>{selected.ai_response || '—'}</Markdown>
                    </div>
                  </div>
                </CardBody>
              </GlowCard>

              {(selected.comment || selected.suggested_response || selected.tags?.length) && (
                <GlowCard accent="#8b5cf6">
                  <CardBody className="space-y-4 pt-5">
                    {selected.tags && selected.tags.length > 0 && (
                      <div className="space-y-1.5">
                        <SectionLabel>Categories</SectionLabel>
                        <ul className="flex flex-wrap gap-1.5">
                          {selected.tags.map((tag) => (
                            <li key={tag}>
                              <Badge tone="brand">
                                {FEEDBACK_CATEGORY_LABELS[tag as FeedbackCategoryValue] ?? tag}
                              </Badge>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selected.comment && (
                      <div className="space-y-1.5">
                        <SectionLabel>Reviewer note</SectionLabel>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-content-muted">
                          {selected.comment}
                        </p>
                      </div>
                    )}

                    {selected.suggested_response && (
                      <div className="space-y-1.5">
                        <SectionLabel>Suggested answer</SectionLabel>
                        <div className="rounded-lg border border-ok/20 bg-ok/[0.04] p-3">
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-content-muted">
                            {selected.suggested_response}
                          </p>
                        </div>
                      </div>
                    )}
                  </CardBody>
                </GlowCard>
              )}

              {tab === 'pending' && selected.status === 'PENDING' && (
                <GlowCard accent="#f59e0b">
                  <CardBody className="space-y-3 pt-5">
                    <label htmlFor="review-note" className="sr-only">
                      Review note
                    </label>
                    <Textarea
                      id="review-note"
                      value={reviewNote}
                      onChange={(e) => setReviewNote(e.target.value)}
                      rows={2}
                      maxLength={1000}
                      placeholder="Optional note for the person who submitted this…"
                    />
                    <div className="flex flex-wrap gap-2">
                      <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                        <Button
                          variant="primary"
                          size="sm"
                          loading={review.isPending}
                          onClick={() => review.mutate({ id: selected.id, status: 'APPROVED' })}
                        >
                          <Check className="h-3.5 w-3.5" aria-hidden />
                          Approve for training
                        </Button>
                      </motion.div>
                      <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={review.isPending}
                          onClick={() => review.mutate({ id: selected.id, status: 'DENIED' })}
                          className="text-danger hover:bg-danger/10"
                        >
                          <X className="h-3.5 w-3.5" aria-hidden />
                          Decline
                        </Button>
                      </motion.div>
                    </div>
                  </CardBody>
                </GlowCard>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
