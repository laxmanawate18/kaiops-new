import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, PanelLeftClose, PanelLeftOpen, Siren, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { chatApi, feedbackApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { ApiError } from '@/lib/api/client'
import { streamChatMessage } from '@/lib/api/stream'
import type { ChatMessage, FeedbackCategoryValue } from '@/lib/api/types'
import { SessionList } from '@/components/chat/SessionList'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { Composer } from '@/components/chat/Composer'
import { LiveReasoning } from '@/components/chat/ReasoningTimeline'
import { FeedbackDialog, type FeedbackDraft } from '@/components/chat/FeedbackDialog'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Tooltip } from '@/components/ui/primitives'
import { cn } from '@/lib/utils'
import { applyFavicon, applyTitle } from '@/lib/chrome'

const SUGGESTIONS = [
  {
    title: 'Diagnose a failing service',
    prompt: 'The payments service is returning 500s in production. Run a root cause analysis.',
  },
  {
    title: 'Check deployment state',
    prompt: 'What changed in the last deploy of the checkout service, and is ArgoCD in sync?',
  },
  {
    title: 'Investigate a crash loop',
    prompt: 'A pod is in CrashLoopBackOff. Pull the recent logs and events and tell me why.',
  },
  {
    title: 'Review the registry',
    prompt: 'List every application currently registered and its cloud provider.',
  },
]

export default function ConsolePage() {
  const { sessionId: routeSessionId } = useParams<{ sessionId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeId, setActiveId] = useState<string | null>(routeSessionId ?? null)
  const [panelOpen, setPanelOpen] = useState(true)
  const [elapsed, setElapsed] = useState(0)
  const [simulateOpen, setSimulateOpen] = useState(false)
  const [feedbackTarget, setFeedbackTarget] = useState<{ message: ChatMessage; userText: string } | null>(
    null,
  )

  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  /* ------------------------------------------------------------ Queries */

  const sessionsQuery = useQuery({
    queryKey: qk.sessions,
    queryFn: () => chatApi.listSessions(true),
    // The background worker creates autonomous (runtime) RCA sessions over time
    // (e.g. from the Slack deep-link or the ArgoCD poller). Poll every 30s and
    // refetch on window focus so a newly-created runtime session shows up in the
    // left panel without requiring a manual reload.
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  })

  const sessions = useMemo(() => sessionsQuery.data?.sessions ?? [], [sessionsQuery.data])

  const messagesQuery = useQuery({
    queryKey: qk.messages(activeId ?? ''),
    queryFn: () => chatApi.listMessages(activeId as string),
    enabled: Boolean(activeId),
  })

  const messages = useMemo(() => messagesQuery.data?.messages ?? [], [messagesQuery.data])

  // Persisted votes: message_id -> 'up' | 'down'. Keeps thumbs state alive
  // across reloads (bug H4) and hydrates MessageBubble after refetches.
  const myFeedbackQuery = useQuery({
    queryKey: qk.feedbackMine,
    queryFn: () => feedbackApi.mine(100),
    staleTime: 60_000,
  })
  const voteMap = useMemo(() => {
    const map = new Map<string, 'up' | 'down'>()
    for (const fb of myFeedbackQuery.data ?? []) {
      if (!fb.message_id) continue
      if (fb.feedback_type === 'THUMBS_UP') map.set(fb.message_id, 'up')
      else if (fb.feedback_type === 'THUMBS_DOWN') map.set(fb.message_id, 'down')
    }
    return map
  }, [myFeedbackQuery.data])

  /* -------------------------------------------------------- Mutations */

  const createSession = useMutation({
    mutationFn: (name?: string) => chatApi.createSession(name),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: qk.sessions })
      selectSession(data.session.id)
    },
    onError: (error: ApiError) => toast.error('Could not start an investigation', { description: error.message }),
  })

  const sendMessage = useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) => {
      // Preferred path: SSE streaming — text appears as the agent thinks.
      try {
        let accumulated = ''
        const streamId = `streaming-${Date.now()}`

        const upsertPlaceholder = (patch: Partial<ChatMessage>) => {
          queryClient.setQueryData(qk.messages(id), (old: typeof messagesQuery.data) => {
            const list = old?.messages ?? []
            const idx = list.findIndex((m) => m.id === streamId)
            const base: ChatMessage = idx >= 0 ? list[idx] : {
              id: streamId,
              session_id: id,
              user_id: 'agent',
              sender: 'assistant',
              text: '',
              timestamp: new Date().toISOString(),
              metadata: {},
            }
            const next = { ...base, ...patch }
            const messages = idx >= 0
              ? list.map((m) => (m.id === streamId ? next : m))
              : [...list, next]
            return { session_id: id, messages, total: old?.total ?? messages.length }
          })
        }

        await streamChatMessage(id, text, {
          onDelta: (delta) => {
            accumulated += delta
            upsertPlaceholder({ text: accumulated })
          },
          onReasoning: (step) => {
            queryClient.setQueryData(qk.messages(id), (old: typeof messagesQuery.data) => {
              const list = old?.messages ?? []
              return {
                session_id: id,
                messages: list.map((m) =>
                  m.id === streamId
                    ? {
                        ...m,
                        metadata: {
                          ...m.metadata,
                          reasoning_steps: [
                            ...(((m.metadata?.reasoning_steps ?? []) as unknown[])),
                            step,
                          ],
                        },
                      }
                    : m,
                ),
                total: old?.total ?? list.length,
              }
            })
          },
        })

        // Stream finished — refetch for server-authoritative ids/metadata.
        await queryClient.invalidateQueries({ queryKey: qk.messages(id) })
        return null
      } catch {
        // Streaming unavailable (proxy, network, older backend) — fall back
        // to the blocking endpoint so sending always works.
        return chatApi.sendMessage(id, text)
      }
    },
    onMutate: async ({ id, text }) => {
      // Optimistically show the user's turn so the UI never feels stalled.
      await queryClient.cancelQueries({ queryKey: qk.messages(id) })
      const previous = queryClient.getQueryData(qk.messages(id))
      const optimistic: ChatMessage = {
        id: `optimistic-${Date.now()}`,
        session_id: id,
        user_id: 'me',
        sender: 'user',
        text,
        timestamp: new Date().toISOString(),
        metadata: {},
      }
      queryClient.setQueryData(qk.messages(id), (old: typeof messagesQuery.data) => ({
        session_id: id,
        messages: [...(old?.messages ?? []), optimistic],
        total: (old?.total ?? 0) + 1,
      }))
      return { previous }
    },
    onError: (error: ApiError, variables, context) => {
      // Roll back the optimistic turn — leaving it would imply it was sent.
      if (context?.previous) queryClient.setQueryData(qk.messages(variables.id), context.previous)
      toast.error('The agent could not be reached', { description: error.message })
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.messages(variables.id) })
      queryClient.invalidateQueries({ queryKey: qk.sessions })
    },
  })

  const approveAction = useMutation({
    mutationFn: ({ id, token }: { id: string; token: string }) => chatApi.approveAction(id, token),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.messages(variables.id) })
      toast.success('Action approved and executed')
    },
    onError: (error: ApiError) => toast.error('Approval failed', { description: error.message }),
  })

  const rejectAction = useMutation({
    mutationFn: ({ id, token }: { id: string; token: string }) => chatApi.rejectAction(id, token),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.messages(variables.id) })
      toast.success('Action rejected')
    },
    onError: (error: ApiError) => toast.error('Rejection failed', { description: error.message }),
  })

  const renameSession = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => chatApi.renameSession(id, name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.sessions }),
    onError: (error: ApiError) => toast.error('Rename failed', { description: error.message }),
  })

  const deleteSession = useMutation({
    mutationFn: (id: string) => chatApi.deleteSession(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: qk.sessions })
      if (id === activeId) {
        const next = sessions.find((s) => s.id !== id)
        selectSession(next?.id ?? null)
      }
      toast.success('Investigation deleted')
    },
    onError: (error: ApiError) => toast.error('Delete failed', { description: error.message }),
  })

  const simulateIncident = useMutation({
    mutationFn: () => chatApi.simulateIncident(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: qk.sessions })
      selectSession(data.session_id)
      toast.warning('P0 incident simulated', { description: data.incident_name })
    },
    onError: (error: ApiError) => toast.error('Simulation failed', { description: error.message }),
  })

  const submitFeedback = useMutation({
    mutationFn: (vars: {
      message: ChatMessage
      userText: string
      type: 'THUMBS_UP' | 'THUMBS_DOWN'
      tags?: FeedbackCategoryValue[]
      comment?: string
      suggested?: string
    }) =>
      feedbackApi.create({
        conversation_id: vars.message.session_id,
        message_id: vars.message.id,
        user_message: vars.userText,
        ai_response: vars.message.text,
        feedback_type: vars.type,
        rating: vars.type === 'THUMBS_UP' ? 5 : 2,
        tags: vars.tags ?? (vars.type === 'THUMBS_UP' ? ['helpfulness'] : []),
        comment: vars.comment || undefined,
        suggested_response: vars.suggested || undefined,
      }),
    onSuccess: () => {
      toast.success('Thanks — that helps', { description: 'Your feedback is queued for review.' })
      setFeedbackTarget(null)
      queryClient.invalidateQueries({ queryKey: qk.feedbackMine })
    },
    onError: (error: ApiError) =>
      toast.error('Feedback could not be saved', { description: error.message }),
  })

  /* ---------------------------------------------------------- Effects */

  const selectSession = useCallback(
    (id: string | null) => {
      setActiveId(id)
      navigate(id ? `/console/${id}` : '/console', { replace: true })
    },
    [navigate],
  )

  // Default to the most recent session on first load.
  useEffect(() => {
    if (activeId || sessions.length === 0) return
    if (routeSessionId) return
    setActiveId(sessions[0].id)
  }, [sessions, activeId, routeSessionId])

  // Honour ?new=1 and ?simulate=1 from the command palette.
  useEffect(() => {
    if (searchParams.get('new') === '1') {
      searchParams.delete('new')
      setSearchParams(searchParams, { replace: true })
      createSession.mutate(undefined)
    }
    if (searchParams.get('simulate') === '1') {
      searchParams.delete('simulate')
      setSearchParams(searchParams, { replace: true })
      setSimulateOpen(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  /**
   * A seed prompt left by "Investigate" on a service page.
   *
   * Read-and-clear so a later refresh doesn't silently re-send it — that was
   * the shape of a real double-send bug in the previous build.
   */
  useEffect(() => {
    const seed = sessionStorage.getItem('kaiops.seedPrompt')
    if (!seed) return
    sessionStorage.removeItem('kaiops.seedPrompt')
    // Prefer the session the service page navigated us to — creating a fresh
    // one here orphaned the seeded message in a session the user never saw.
    const target = routeSessionId ?? activeId
    if (target) {
      sendMessage.mutate({ id: target, text: seed })
    } else {
      createSession.mutate(undefined, {
        onSuccess: (data) => {
          selectSession(data.session.id)
          sendMessage.mutate({ id: data.session.id, text: seed })
        },
      })
    }
    // Run once on mount; route/active ids are read at call time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Elapsed timer for the live reasoning panel.
  useEffect(() => {
    if (!sendMessage.isPending) {
      setElapsed(0)
      return
    }
    const started = Date.now()
    const interval = setInterval(() => setElapsed(Date.now() - started), 250)
    return () => clearInterval(interval)
  }, [sendMessage.isPending])

  // Keep the newest message in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, sendMessage.isPending])

  // ── A2: incident favicon — flip when the open thread shows a critical finding ──
  useEffect(() => {
    const lastAssistant = [...messages].reverse().find((m) => m.sender === 'assistant')
    const critical =
      !!lastAssistant &&
      ((lastAssistant.metadata?.severity === 'P0' ||
        lastAssistant.metadata?.severity === 'P1') ||
        /🔴|critical/i.test(lastAssistant.text.slice(0, 400)))
    applyFavicon(critical)
    if (critical) document.title = `🔴 KaiOps · Console`
    else applyTitle('/console')
  }, [messages])

  /* ----------------------------------------------------------- Handlers */

  const handleSend = (text: string) => {
    if (!activeId) {
      // No session yet — create one, then send once it exists.
      createSession.mutate(undefined, {
        onSuccess: (data) => sendMessage.mutate({ id: data.session.id, text }),
      })
      return
    }
    sendMessage.mutate({ id: activeId, text })
  }

  const handleApproval = (decision: 'approve' | 'reject', token: string) => {
    if (!activeId || !token) return
    if (decision === 'approve') {
      approveAction.mutate({ id: activeId, token })
    } else {
      rejectAction.mutate({ id: activeId, token })
    }
  }

  const handleFeedback = (message: ChatMessage, kind: 'up' | 'down', userText: string) => {
    if (kind === 'up') {
      submitFeedback.mutate({ message, userText, type: 'THUMBS_UP' })
    } else {
      setFeedbackTarget({ message, userText })
    }
  }

  /** The user turn immediately before an assistant message. */
  const precedingUserText = useCallback(
    (index: number) => {
      for (let i = index - 1; i >= 0; i -= 1) {
        if (messages[i]?.sender === 'user') return messages[i].text
      }
      return 'User query'
    },
    [messages],
  )

  const activeSession = sessions.find((s) => s.id === activeId)
  const busy = sendMessage.isPending

  /* -------------------------------------------------------------- View */

  return (
    <div className="flex h-full">
      {/* Session rail */}
      <AnimatePresence initial={false}>
        {panelOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 264, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="shrink-0 overflow-hidden"
          >
            <div className="h-full w-[264px]">
              <SessionList
                sessions={sessions}
                activeId={activeId}
                loading={sessionsQuery.isLoading}
                creating={createSession.isPending}
                onSelect={selectSession}
                onCreate={() => createSession.mutate(undefined)}
                onRename={(id, name) => renameSession.mutate({ id, name })}
                onDelete={(id) => deleteSession.mutate(id)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Conversation */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="flex h-12 shrink-0 items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-4 backdrop-blur-sm">
          <Tooltip content={panelOpen ? 'Hide investigations' : 'Show investigations'}>
            <button
              type="button"
              onClick={() => setPanelOpen((v) => !v)}
              aria-label={panelOpen ? 'Hide investigations panel' : 'Show investigations panel'}
              aria-expanded={panelOpen}
              className="rounded-md p-1.5 text-content-subtle transition-colors hover:bg-surface-raised hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              {panelOpen ? (
                <PanelLeftClose className="h-4 w-4" aria-hidden />
              ) : (
                <PanelLeftOpen className="h-4 w-4" aria-hidden />
              )}
            </button>
          </Tooltip>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-sm font-medium text-content">
              {activeSession?.name ?? 'New investigation'}
            </h1>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSimulateOpen(true)}
            className="text-danger hover:bg-danger/10 hover:text-danger"
          >
            <Siren className="h-3.5 w-3.5" aria-hidden />
            <span className="hidden sm:inline">Simulate P0</span>
          </Button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          <div className="mx-auto w-full max-w-4xl px-4 py-6">
            {messagesQuery.isLoading && activeId ? (
              <div className="space-y-6">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <Skeleton className="h-7 w-7 rounded-lg" />
                    <Skeleton className="h-20 flex-1 rounded-2xl" />
                  </div>
                ))}
              </div>
            ) : messagesQuery.isError ? (
              <ErrorState
                title="Could not load this conversation"
                message={(messagesQuery.error as ApiError)?.message}
                onRetry={() => messagesQuery.refetch()}
                retrying={messagesQuery.isFetching}
              />
            ) : messages.length === 0 ? (
              <WelcomePanel onPick={handleSend} disabled={busy || createSession.isPending} />
            ) : (
              <div className="space-y-6">
                <AnimatePresence initial={false}>
                  {messages.map((message, index) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 22, scale: 0.97 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                    >
                      <MessageBubble
                        message={message}
                        precedingUserText={precedingUserText(index)}
                        onFeedback={handleFeedback}
                        onApprovalDecision={handleApproval}
                        approvalPending={approveAction.isPending || rejectAction.isPending}
                        busy={busy}
                        initialVote={voteMap.get(message.id) ?? null}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}

            <AnimatePresence>
              {busy && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mt-6 pl-10"
                >
                  <LiveReasoning elapsedMs={elapsed} />
                </motion.div>
              )}
            </AnimatePresence>

            <div ref={bottomRef} className="h-1" />
          </div>
        </div>

        {/* Composer */}
        <div className="shrink-0 border-t border-white/[0.06] bg-white/[0.02] backdrop-blur-xl">
          <div className="mx-auto w-full max-w-4xl">
            <Composer onSend={handleSend} busy={busy} disabled={createSession.isPending} />
          </div>
        </div>
      </div>

      {/* Dialogs */}
      <ConfirmDialog
        open={simulateOpen}
        onOpenChange={setSimulateOpen}
        onConfirm={() => {
          setSimulateOpen(false)
          simulateIncident.mutate()
        }}
        tone="warning"
        title="Simulate a P0 outage?"
        description="This creates a new incident war-room session and runs the full multi-agent RCA pipeline against a synthetic payment-gateway outage. It does not touch production."
        confirmText="Run simulation"
        loading={simulateIncident.isPending}
      />

      <FeedbackDialog
        open={feedbackTarget !== null}
        onOpenChange={(open) => !open && setFeedbackTarget(null)}
        submitting={submitFeedback.isPending}
        onSubmit={(draft: FeedbackDraft) => {
          if (!feedbackTarget) return
          submitFeedback.mutate({
            message: feedbackTarget.message,
            userText: feedbackTarget.userText,
            type: 'THUMBS_DOWN',
            tags: draft.tags,
            comment: draft.comment,
            suggested: draft.suggested_response,
          })
        }}
      />
    </div>
  )
}

/* ------------------------------------------------------------- Welcome */

function SuggestionCard({
  title, prompt, index, onPick, disabled,
}: { title: string; prompt: string; index: number; onPick: (p: string) => void; disabled?: boolean }) {
  const ref = useRef<HTMLButtonElement>(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [glow, setGlow] = useState({ x: 50, y: 50, show: false })

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top)  / r.height
    setTilt({ x: (py - 0.5) * -10, y: (px - 0.5) * 10 })
    setGlow({ x: px * 100, y: py * 100, show: true })
  }
  const reset = () => { setTilt({ x: 0, y: 0 }); setGlow(g => ({ ...g, show: false })) }

  return (
    <motion.button
      ref={ref}
      type="button"
      disabled={disabled}
      onClick={() => onPick(prompt)}
      onMouseMove={onMove}
      onMouseLeave={reset}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 + index * 0.08, type: 'spring', stiffness: 380, damping: 32 }}
      style={{
        transform: `perspective(700px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: 'transform 0.12s ease-out, box-shadow 0.2s ease',
      }}
      className={cn(
        'relative overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.03] p-4 text-left',
        'backdrop-blur-sm',
        'hover:border-cyan-500/30 hover:shadow-[0_0_30px_rgba(6,182,212,0.08)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/40',
        'disabled:pointer-events-none disabled:opacity-40',
      )}
    >
      {/* Cursor glow */}
      <span
        className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 h-24 w-24 rounded-full transition-opacity duration-300"
        style={{
          left: `${glow.x}%`, top: `${glow.y}%`,
          background: 'radial-gradient(circle, rgba(6,182,212,0.15), transparent 70%)',
          opacity: glow.show ? 1 : 0,
        }}
        aria-hidden
      />
      <p className="relative mb-1.5 text-xs font-semibold text-white/80">{title}</p>
      <p className="relative text-[11px] leading-relaxed text-white/35">{prompt}</p>
    </motion.button>
  )
}

function WelcomePanel({ onPick, disabled }: { onPick: (prompt: string) => void; disabled?: boolean }) {
  return (
    <div className="flex flex-col items-center py-12 text-center">
      {/* Animated logo mark */}
      <motion.div
        className="relative mb-6"
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 22, delay: 0.1 }}
      >
        <motion.div
          className="absolute inset-0 rounded-2xl blur-2xl"
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.5), rgba(139,92,246,0.3))' }}
          aria-hidden
        />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-500/25 bg-cyan-500/10 shadow-[0_0_40px_rgba(6,182,212,0.15)]">
          <Sparkles className="h-7 w-7 text-cyan-300" aria-hidden />
        </div>
      </motion.div>

      <motion.h2
        className="mb-2.5 text-2xl font-bold tracking-tight text-white"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        What are we investigating?
      </motion.h2>
      <motion.p
        className="mb-10 max-w-md text-[13px] leading-relaxed text-white/40"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.26, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        Describe the symptom — KaiOPS correlates logs, metrics and deploy state across your cloud fleet.
      </motion.p>

      <div className="grid w-full max-w-2xl gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s, i) => (
          <SuggestionCard key={s.title} {...s} index={i} onPick={onPick} disabled={disabled} />
        ))}
      </div>

      <motion.p
        className="mt-8 flex items-center gap-1.5 text-[11px] text-white/20"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
      >
        <AlertTriangle className="h-3 w-3" aria-hidden />
        Verify findings before acting on them in production.
      </motion.p>
    </div>
  )
}
