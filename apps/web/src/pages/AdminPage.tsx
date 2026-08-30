import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Search, ShieldCheck, Trash2, UserCog, Users2 } from 'lucide-react'
import { toast } from 'sonner'
import { authApi, teamsApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { ApiError } from '@/lib/api/client'
import type { User, UserRole } from '@/lib/api/types'
import { useAuth } from '@/lib/auth/AuthProvider'
import {
  Avatar,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  SectionLabel,
  Switch,
  Tabs,
  TabsList,
  TabsTrigger,
  Tooltip,
} from '@/components/ui/primitives'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { Skeleton, SkeletonRow } from '@/components/ui/Skeleton'
import { cn, formatRelative } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'

const ROLES: { value: UserRole; label: string; tone: 'accent' | 'brand' | 'neutral' }[] = [
  { value: 'admin', label: 'Admin', tone: 'accent' },
  { value: 'team_lead', label: 'Team lead', tone: 'brand' },
  { value: 'user', label: 'Engineer', tone: 'neutral' },
]

export default function AdminPage() {
  const [tab, setTab] = useState<'users' | 'teams'>('users')

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="space-y-3">
          <div className="space-y-1">
            <SectionLabel className="text-brand-400">Administration</SectionLabel>
            <h1 className="text-xl font-semibold tracking-tight text-content">Access control</h1>
            <p className="text-xs text-content-subtle">
              Roles are enforced server-side on every request — this screen is the control surface,
              not the guard.
            </p>
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
            <TabsList>
              <TabsTrigger value="users">
                <UserCog className="mr-1.5 inline h-3.5 w-3.5" aria-hidden />
                Users
              </TabsTrigger>
              <TabsTrigger value="teams">
                <Users2 className="mr-1.5 inline h-3.5 w-3.5" aria-hidden />
                Teams
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {tab === 'users' ? <UsersPanel /> : <TeamsPanel />}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ Users */

function UsersPanel() {
  const queryClient = useQueryClient()
  const { user: me } = useAuth()
  const [query, setQuery] = useState('')
  const [pendingDelete, setPendingDelete] = useState<User | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: qk.users,
    queryFn: authApi.listUsers,
  })

  const users = useMemo(() => {
    const list = data ?? []
    const q = query.trim().toLowerCase()
    if (!q) return list
    return list.filter((u) =>
      [u.username, u.email, u.full_name].filter(Boolean).some((f) => String(f).toLowerCase().includes(q)),
    )
  }, [data, query])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: qk.users })

  const setRole = useMutation({
    mutationFn: ({ username, role }: { username: string; role: UserRole }) =>
      authApi.updateUserRole(username, role),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(`${v.username} is now ${ROLES.find((r) => r.value === v.role)?.label}`)
    },
    onError: (e: ApiError) => toast.error('Could not change role', { description: e.message }),
  })

  const setActive = useMutation({
    mutationFn: ({ username, isActive }: { username: string; isActive: boolean }) =>
      authApi.toggleUserActive(username, isActive),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(`${v.username} ${v.isActive ? 'activated' : 'deactivated'}`)
    },
    onError: (e: ApiError) => toast.error('Could not change status', { description: e.message }),
  })

  const removeUser = useMutation({
    mutationFn: (username: string) => authApi.deleteUser(username),
    onSuccess: (_d, username) => {
      invalidate()
      toast.success(`${username} deleted`)
      setPendingDelete(null)
    },
    onError: (e: ApiError) => toast.error('Could not delete user', { description: e.message }),
  })

  if (isError) {
    return (
      <ErrorState
        title="Could not load users"
        message={(error as ApiError)?.message}
        onRetry={() => refetch()}
      />
    )
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="space-y-0.5">
            <CardTitle>Users</CardTitle>
            <p className="text-2xs text-content-subtle" aria-live="polite">
              {isLoading ? 'Loading…' : `${users.length} user${users.length === 1 ? '' : 's'}`}
            </p>
          </div>
          <div className="w-56">
            <label htmlFor="user-search" className="sr-only">
              Search users
            </label>
            <Input
              id="user-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search…"
              className="h-8 text-xs"
              leadingIcon={<Search className="h-3.5 w-3.5" />}
            />
          </div>
        </CardHeader>

        <CardBody className="px-0 pb-0">
          {isLoading ? (
            <div className="divide-y divide-line">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonRow key={i} columns={4} />
              ))}
            </div>
          ) : users.length === 0 ? (
            <EmptyState size="sm" icon={UserCog} title="No users match" />
          ) : (
            <motion.ul
              variants={staggerContainer(0.03)}
              initial="initial"
              animate="animate"
              className="divide-y divide-line"
            >
              {users.map((user) => {
                const isSelf = user.username === me?.username
                return (
                  <motion.li
                    key={user.id}
                    variants={staggerItem}
                    className="flex flex-wrap items-center gap-4 px-5 py-3.5 transition-colors hover:bg-surface-raised/30"
                  >
                    <Avatar name={user.full_name || user.username} size="sm" />

                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 truncate text-sm font-medium text-content">
                        {user.full_name || user.username}
                        {isSelf && (
                          <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-[10px] text-content-subtle">
                            you
                          </span>
                        )}
                      </p>
                      <p className="truncate text-2xs text-content-subtle">{user.email}</p>
                    </div>

                    {user.teams && user.teams.length > 0 && (
                      <div className="hidden lg:block">
                        <Badge tone="neutral" size="sm">
                          {user.teams.length} team{user.teams.length === 1 ? '' : 's'}
                        </Badge>
                      </div>
                    )}

                    <p className="hidden w-24 font-mono text-2xs text-content-subtle sm:block">
                      {formatRelative(user.created_at)}
                    </p>

                    {/* Role */}
                    <div>
                      <label htmlFor={`role-${user.id}`} className="sr-only">
                        Role for {user.username}
                      </label>
                      <select
                        id={`role-${user.id}`}
                        value={user.role}
                        disabled={isSelf || setRole.isPending}
                        onChange={(e) =>
                          setRole.mutate({ username: user.username, role: e.target.value as UserRole })
                        }
                        className={cn(
                          'h-8 rounded-md border border-line-strong bg-surface-sunken/60 px-2 text-xs text-content',
                          'focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-ring/50',
                          'disabled:cursor-not-allowed disabled:opacity-50',
                        )}
                      >
                        {ROLES.map((role) => (
                          <option key={role.value} value={role.value}>
                            {role.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Active */}
                    <Tooltip content={isSelf ? 'You cannot deactivate yourself' : 'Active'}>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={user.is_active}
                          disabled={isSelf || setActive.isPending}
                          onCheckedChange={(checked) =>
                            setActive.mutate({ username: user.username, isActive: checked })
                          }
                          aria-label={`${user.username} is ${user.is_active ? 'active' : 'inactive'}`}
                        />
                      </div>
                    </Tooltip>

                    <Tooltip content={isSelf ? 'You cannot delete yourself' : 'Delete user'}>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        disabled={isSelf}
                        onClick={() => setPendingDelete(user)}
                        aria-label={`Delete ${user.username}`}
                        className="text-danger hover:bg-danger/10 disabled:opacity-30"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </Button>
                    </Tooltip>
                  </motion.li>
                )
              })}
            </motion.ul>
          )}
        </CardBody>
      </Card>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) removeUser.mutate(pendingDelete.username)
        }}
        loading={removeUser.isPending}
        title={`Delete ${pendingDelete?.username}?`}
        description="Their account is removed permanently. Their past investigations and feedback remain."
        confirmText="Delete user"
        tone="danger"
      />
    </>
  )
}

/* ------------------------------------------------------------------ Teams */

function TeamsPanel() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: qk.teams,
    queryFn: teamsApi.list,
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <ErrorState
        title="Could not load teams"
        message={(error as ApiError)?.message}
        onRetry={() => refetch()}
      />
    )
  }

  const teams = data ?? []

  if (teams.length === 0) {
    return (
      <EmptyState
        icon={Users2}
        title="No teams yet"
        description="Teams group engineers and control which agents they can reach."
      />
    )
  }

  return (
    <motion.div
      variants={staggerContainer(0.04)}
      initial="initial"
      animate="animate"
      className="grid gap-4 sm:grid-cols-2"
    >
      {teams.map((team) => (
        <motion.div key={team.id} variants={staggerItem}>
          <Card className="h-full p-5">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-content">{team.name}</h3>
                <p className="mt-0.5 line-clamp-2 text-2xs text-content-subtle">
                  {team.description || 'No description'}
                </p>
              </div>
              <Badge tone={team.is_active ? 'ok' : 'neutral'} dot>
                {team.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </div>

            <div className="flex items-center gap-4 border-t border-line pt-3">
              <div className="flex items-center gap-1.5 text-2xs text-content-muted">
                <Users2 className="h-3.5 w-3.5" aria-hidden />
                {team.member_count ?? 0} member{team.member_count === 1 ? '' : 's'}
              </div>
              {team.team_lead_username && (
                <div className="flex items-center gap-1.5 text-2xs text-content-muted">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                  {team.team_lead_username}
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      ))}
    </motion.div>
  )
}
