import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { MessageSquare, MoreHorizontal, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import type { ChatSession } from '@/lib/api/types'
import { cn, formatRelative } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { ConfirmDialog } from '@/components/ui/Dialog'

interface SessionListProps {
  sessions: ChatSession[]
  activeId: string | null
  loading?: boolean
  onSelect: (id: string) => void
  onCreate: () => void
  onRename: (id: string, name: string) => void
  onDelete: (id: string) => void
  creating?: boolean
}

export function SessionList({
  sessions,
  activeId,
  loading,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  creating,
}: SessionListProps) {
  const [query, setQuery] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftName, setDraftName] = useState('')
  const [pendingDelete, setPendingDelete] = useState<ChatSession | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter((s) => (s.name ?? '').toLowerCase().includes(q))
  }, [sessions, query])

  const commitRename = (id: string) => {
    const trimmed = draftName.trim()
    const original = sessions.find((s) => s.id === id)?.name
    if (trimmed && trimmed !== original) onRename(id, trimmed)
    setEditingId(null)
    setDraftName('')
  }

  return (
    <div className="flex h-full flex-col border-r border-line bg-surface/40">
      <div className="space-y-3 border-b border-line p-3">
        <Button variant="primary" size="sm" onClick={onCreate} loading={creating} className="w-full">
          {!creating && <Plus className="h-3.5 w-3.5" aria-hidden />}
          New investigation
        </Button>

        <div>
          <label htmlFor="session-search" className="sr-only">
            Search investigations
          </label>
          <Input
            id="session-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="h-8 text-xs"
            leadingIcon={<Search className="h-3.5 w-3.5" />}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-2">
        {loading ? (
          <div className="space-y-1.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-lg" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            size="sm"
            icon={MessageSquare}
            title={query ? 'No matches' : 'No investigations yet'}
            description={
              query ? 'Try a different search term.' : 'Start one to begin diagnosing an incident.'
            }
          />
        ) : (
          <ul className="space-y-0.5">
            <AnimatePresence initial={false}>
              {filtered.map((session) => {
                const active = session.id === activeId
                const isEditing = editingId === session.id

                return (
                  <motion.li
                    key={session.id}
                    layout
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                    className="group relative"
                  >
                    {isEditing ? (
                      <div className="p-1">
                        <Input
                          autoFocus
                          value={draftName}
                          onChange={(e) => setDraftName(e.target.value)}
                          onBlur={() => commitRename(session.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') commitRename(session.id)
                            if (e.key === 'Escape') {
                              setEditingId(null)
                              setDraftName('')
                            }
                          }}
                          className="h-8 text-xs"
                          aria-label="Session name"
                        />
                      </div>
                    ) : (
                      <div
                        className={cn(
                          'relative flex items-center gap-2 rounded-lg px-2.5 py-2 transition-colors',
                          active ? 'bg-brand-500/10' : 'hover:bg-surface-raised/60',
                        )}
                      >
                        {active && (
                          <motion.span
                            layoutId="session-active"
                            className="absolute inset-0 rounded-lg border border-brand-500/25"
                            transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                            aria-hidden
                          />
                        )}

                        <button
                          type="button"
                          onClick={() => onSelect(session.id)}
                          aria-current={active ? 'page' : undefined}
                          className="relative flex min-w-0 flex-1 flex-col items-start gap-0.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded"
                        >
                          <span
                            className={cn(
                              'w-full max-w-full truncate text-xs font-medium',
                              active ? 'text-brand-100' : 'text-content-muted',
                            )}
                            title={session.name || 'Untitled'}
                          >
                            {session.name || 'Untitled'}
                          </span>
                          <span className="flex items-center gap-1.5 font-mono text-[10px] text-content-subtle">
                            <span>{session.message_count ?? 0} msg</span>
                            <span aria-hidden>·</span>
                            <span>{formatRelative(session.last_modified)}</span>
                          </span>
                        </button>

                        <DropdownMenu.Root>
                          <DropdownMenu.Trigger
                            aria-label="Session actions"
                            className={cn(
                              'relative shrink-0 rounded p-1 text-content-subtle opacity-0 transition-all',
                              'hover:bg-surface-overlay hover:text-content',
                              'group-hover:opacity-100 data-[state=open]:opacity-100',
                              'focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                            )}
                          >
                            <MoreHorizontal className="h-3.5 w-3.5" aria-hidden />
                          </DropdownMenu.Trigger>
                          <DropdownMenu.Portal>
                            <DropdownMenu.Content
                              align="end"
                              sideOffset={4}
                              className="z-50 w-40 rounded-lg border border-line-strong bg-surface-overlay p-1 shadow-overlay data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
                            >
                              <DropdownMenu.Item
                                onSelect={() => {
                                  setEditingId(session.id)
                                  setDraftName(session.name ?? '')
                                }}
                                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs text-content-muted outline-none data-[highlighted]:bg-surface-raised data-[highlighted]:text-content"
                              >
                                <Pencil className="h-3.5 w-3.5" aria-hidden />
                                Rename
                              </DropdownMenu.Item>
                              <DropdownMenu.Item
                                onSelect={() => setPendingDelete(session)}
                                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs text-danger outline-none data-[highlighted]:bg-danger/10"
                              >
                                <Trash2 className="h-3.5 w-3.5" aria-hidden />
                                Delete
                              </DropdownMenu.Item>
                            </DropdownMenu.Content>
                          </DropdownMenu.Portal>
                        </DropdownMenu.Root>
                      </div>
                    )}
                  </motion.li>
                )
              })}
            </AnimatePresence>
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete.id)
          setPendingDelete(null)
        }}
        title="Delete this investigation?"
        description={
          <>
            <span className="font-medium text-content">{pendingDelete?.name}</span> and all of its
            messages will be permanently removed. This cannot be undone.
          </>
        }
        confirmText="Delete"
        tone="danger"
      />
    </div>
  )
}
