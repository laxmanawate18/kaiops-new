import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { ChevronDown, LogOut, Search, ShieldCheck, User as UserIcon } from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthProvider'
import { useUiStore } from '@/stores/ui'
import { systemApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { Avatar } from '@/components/ui/primitives'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import { useIsMac } from '@/hooks/useIsMac'

const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrator',
  team_lead: 'Team lead',
  user: 'Engineer',
}

export function TopBar() {
  const { user, logout, isAdmin, isTeamLead } = useAuth()
  const navigate = useNavigate()
  const setCommandOpen = useUiStore((s) => s.setCommandOpen)
  const isMac = useIsMac()

  // Health drives a single pill. Polls slowly — this is ambient, not critical.
  const { data: health, isError: healthError } = useQuery({
    queryKey: qk.health,
    queryFn: systemApi.health,
    refetchInterval: 60_000,
    retry: false,
  })

  const healthy = !healthError && health?.status === 'healthy'

  return (
    <header className="relative z-20 flex h-16 shrink-0 items-center gap-4 border-b border-line bg-surface/60 px-5 backdrop-blur-xl">
      {/* Command trigger doubles as the app-wide search affordance. */}
      <button
        type="button"
        onClick={() => setCommandOpen(true)}
        className={cn(
          'group flex h-9 min-w-0 flex-1 max-w-md items-center gap-2.5 rounded-lg border border-line-strong',
          'bg-surface-sunken/60 px-3 text-left text-sm text-content-subtle',
          'transition-colors hover:border-brand-500/40 hover:bg-surface-sunken',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-content-subtle group-hover:text-brand-300" aria-hidden />
        <span className="truncate">Search services, sessions, actions…</span>
        <kbd className="ml-auto hidden shrink-0 items-center gap-0.5 rounded border border-line-strong bg-surface-overlay px-1.5 py-0.5 font-mono text-2xs text-content-subtle sm:flex">
          {isMac ? '⌘' : 'Ctrl'} K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-3">
        {/* System health */}
        <span
          title={
            healthy
              ? 'All systems operational — backend, database and integrations reachable.'
              : 'Backend health check is failing or unreachable.'
          }
        >
          <Badge tone={healthy ? 'ok' : 'warn'} dot pulse={healthy} className="hidden sm:inline-flex">
            {healthy ? 'Systems nominal' : 'API unreachable'}
          </Badge>
        </span>

        {/* Account */}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            className={cn(
              'flex items-center gap-2 rounded-lg border border-line-strong bg-surface-raised/70 py-1 pl-1 pr-2',
              'transition-colors hover:border-brand-500/30 hover:bg-surface-overlay',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
            )}
          >
            <Avatar name={user?.full_name || user?.username} size="sm" />
            <div className="hidden min-w-0 text-left leading-tight md:block">
              <p className="truncate text-xs font-medium text-content">{user?.username}</p>
              <p className="truncate text-[10px] text-content-subtle">
                {ROLE_LABEL[user?.role ?? 'user'] ?? 'Engineer'}
              </p>
            </div>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-content-subtle" aria-hidden />
          </DropdownMenu.Trigger>

          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className={cn(
                'z-50 w-60 overflow-hidden rounded-xl border border-line-strong bg-surface-overlay p-1.5 shadow-overlay',
                'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
                'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
              )}
            >
              <div className="flex items-center gap-3 px-2.5 py-2.5">
                <Avatar name={user?.full_name || user?.username} size="md" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-content">
                    {user?.full_name || user?.username}
                  </p>
                  <p className="truncate text-xs text-content-subtle">{user?.email}</p>
                </div>
              </div>

              {(isAdmin || isTeamLead) && (
                <div className="px-2.5 pb-2">
                  <Badge tone={isAdmin ? 'accent' : 'brand'} size="sm">
                    <ShieldCheck className="h-3 w-3" aria-hidden />
                    {ROLE_LABEL[user?.role ?? 'user']}
                  </Badge>
                </div>
              )}

              <DropdownMenu.Separator className="my-1 h-px bg-line" />

              <DropdownMenu.Item
                onSelect={() => navigate('/profile')}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-content-muted outline-none transition-colors data-[highlighted]:bg-surface-raised data-[highlighted]:text-content"
              >
                <UserIcon className="h-4 w-4" aria-hidden />
                Profile &amp; security
              </DropdownMenu.Item>

              <DropdownMenu.Item
                onSelect={() => {
                  logout()
                  navigate('/login', { replace: true })
                }}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-danger outline-none transition-colors data-[highlighted]:bg-danger/10"
              >
                <LogOut className="h-4 w-4" aria-hidden />
                Sign out
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  )
}
