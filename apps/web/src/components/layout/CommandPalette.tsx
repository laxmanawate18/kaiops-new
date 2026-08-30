import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Command } from 'cmdk'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import {
  Boxes,
  LayoutDashboard,
  LogOut,
  MessageSquareCode,
  MessagesSquare,
  Plus,
  Search,
  Siren,
  User as UserIcon,
  Users2,
} from 'lucide-react'
import { useUiStore } from '@/stores/ui'
import { useAuth } from '@/lib/auth/AuthProvider'
import { applicationsApi, chatApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { cn, normalizeEnum } from '@/lib/utils'
import { CloudBadge, type CloudProvider } from '@/components/ui/Badge'

/**
 * ⌘K palette.
 *
 * Keyboard-first navigation is table stakes for an operations tool — during
 * an incident nobody wants to hunt through a nav. Sessions and services are
 * searchable inline so you can jump straight to context.
 */
export function CommandPalette() {
  const open = useUiStore((s) => s.commandOpen)
  const setOpen = useUiStore((s) => s.setCommandOpen)
  const navigate = useNavigate()
  const { isAdmin, canManage, logout } = useAuth()

  // Global shortcut.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setOpen(!open)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, setOpen])

  // Only fetch while the palette is open — this shouldn't cost anything at rest.
  const { data: sessionsData } = useQuery({
    queryKey: qk.sessions,
    queryFn: () => chatApi.listSessions(true),
    enabled: open,
    staleTime: 15_000,
  })

  const { data: appsData } = useQuery({
    queryKey: qk.applications({ page_size: 100 }),
    queryFn: () => applicationsApi.list({ page_size: 100 }),
    enabled: open,
    staleTime: 60_000,
  })

  const sessions = useMemo(() => (sessionsData?.sessions ?? []).slice(0, 6), [sessionsData])
  const apps = useMemo(() => appsData?.applications ?? [], [appsData])

  const go = (path: string) => {
    setOpen(false)
    navigate(path)
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className={cn(
            'fixed inset-0 z-50 bg-canvas/80 backdrop-blur-sm',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
          )}
        />
        <DialogPrimitive.Content
          className={cn(
            'fixed left-1/2 top-[16vh] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2',
            'overflow-hidden rounded-2xl border border-line-strong bg-surface-overlay shadow-overlay',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:slide-in-from-top-2',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
          )}
        >
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Search for services, sessions and actions.
          </DialogPrimitive.Description>

          <Command loop className="w-full">
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search className="h-4 w-4 shrink-0 text-content-subtle" aria-hidden />
              <Command.Input
                autoFocus
                placeholder="Search or jump to…"
                className="h-14 flex-1 bg-transparent text-sm text-content outline-none placeholder:text-content-subtle"
              />
              <kbd className="hidden rounded border border-line-strong px-1.5 py-0.5 font-mono text-2xs text-content-subtle sm:block">
                ESC
              </kbd>
            </div>

            <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto scrollbar-thin p-2">
              <Command.Empty className="py-10 text-center text-xs text-content-subtle">
                Nothing matched that.
              </Command.Empty>

              <Group heading="Go to">
                <Item icon={MessageSquareCode} onSelect={() => go('/console')}>
                  Console
                </Item>
                <Item icon={LayoutDashboard} onSelect={() => go('/dashboard')}>
                  Overview
                </Item>
                <Item icon={Boxes} onSelect={() => go('/services')}>
                  Services
                </Item>
                {canManage && (
                  <Item icon={MessagesSquare} onSelect={() => go('/feedback')}>
                    Review queue
                  </Item>
                )}
                {isAdmin && (
                  <Item icon={Users2} onSelect={() => go('/admin')}>
                    Users &amp; teams
                  </Item>
                )}
                <Item icon={UserIcon} onSelect={() => go('/profile')}>
                  Profile
                </Item>
              </Group>

              <Group heading="Actions">
                <Item icon={Plus} onSelect={() => go('/console?new=1')} shortcut="N">
                  Start a new investigation
                </Item>
                {canManage && (
                  <Item icon={Boxes} onSelect={() => go('/services/new')}>
                    Register a service
                  </Item>
                )}
                <Item icon={Siren} onSelect={() => go('/console?simulate=1')} tone="danger">
                  Simulate a P0 incident
                </Item>
              </Group>

              {sessions.length > 0 && (
                <Group heading="Recent investigations">
                  {sessions.map((session) => (
                    <Item
                      key={session.id}
                      icon={MessageSquareCode}
                      onSelect={() => go(`/console/${session.id}`)}
                      value={`session ${session.name} ${session.id}`}
                      meta={`${session.message_count} msg`}
                    >
                      {session.name}
                    </Item>
                  ))}
                </Group>
              )}

              {apps.length > 0 && (
                <Group heading="Services">
                  {apps.slice(0, 8).map((app) => (
                    <Item
                      key={app.id}
                      icon={Boxes}
                      onSelect={() => go(`/services/${app.id}`)}
                      value={`service ${app.application_name} ${app.application_owner ?? ''}`}
                      trailing={
                        <CloudBadge
                          provider={(normalizeEnum(app.cloud_provider) || 'unknown') as CloudProvider}
                        />
                      }
                    >
                      {app.application_name}
                    </Item>
                  ))}
                </Group>
              )}

              <Group heading="Session">
                <Item
                  icon={LogOut}
                  tone="danger"
                  onSelect={() => {
                    setOpen(false)
                    logout()
                    navigate('/login', { replace: true })
                  }}
                >
                  Sign out
                </Item>
              </Group>
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className={cn(
        'mb-1 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5',
        '[&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:font-semibold',
        '[&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.16em]',
        '[&_[cmdk-group-heading]]:text-content-subtle',
      )}
    >
      {children}
    </Command.Group>
  )
}

function Item({
  icon: Icon,
  children,
  onSelect,
  value,
  shortcut,
  meta,
  trailing,
  tone,
}: {
  icon: React.ElementType
  children: React.ReactNode
  onSelect: () => void
  value?: string
  shortcut?: string
  meta?: string
  trailing?: React.ReactNode
  tone?: 'danger'
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      value={value ?? String(children)}
      className={cn(
        'flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors',
        'data-[selected=true]:bg-surface-raised',
        tone === 'danger'
          ? 'text-danger data-[selected=true]:bg-danger/10'
          : 'text-content-muted data-[selected=true]:text-content',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {meta && <span className="shrink-0 font-mono text-2xs text-content-subtle">{meta}</span>}
      {trailing}
      {shortcut && (
        <kbd className="shrink-0 rounded border border-line-strong px-1.5 py-0.5 font-mono text-2xs text-content-subtle">
          {shortcut}
        </kbd>
      )}
    </Command.Item>
  )
}
