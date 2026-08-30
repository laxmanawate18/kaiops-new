import { Suspense, lazy, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Boxes, LayoutGrid, Orbit, Plus, Rows3, Search } from 'lucide-react'
import { applicationsApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import type { Application } from '@/lib/api/types'
import { useAuth } from '@/lib/auth/AuthProvider'
import { useUiStore } from '@/stores/ui'
import { CountUp } from '@/components/ui/CountUp'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { GlowCard, Card, SectionLabel } from '@/components/ui/primitives'
import { CloudBadge, StatusBadge, type CloudProvider, type ServiceStatus } from '@/components/ui/Badge'
import { EmptyState, ErrorState } from '@/components/ui/EmptyState'
import { Skeleton, SkeletonCard } from '@/components/ui/Skeleton'
import { cn, formatRelative, normalizeEnum } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'
import { CanvasBoundary } from '@/components/three/CanvasBoundary'
import type { ApiError } from '@/lib/api/client'

const ServiceTopology = lazy(() => import('@/components/three/ServiceTopology'))

type View = 'grid' | 'list' | 'topology'

const VIEWS: { id: View; label: string; icon: React.ElementType }[] = [
  { id: 'grid', label: 'Grid', icon: LayoutGrid },
  { id: 'list', label: 'List', icon: Rows3 },
  { id: 'topology', label: 'Topology', icon: Orbit },
]

export default function ServicesPage() {
  const { canManage } = useAuth()
  const navigate = useNavigate()
  // View preference persists across reloads (zustand persist).
  const view = useUiStore((s) => s.servicesView)
  const setView = useUiStore((s) => s.setServicesView)
  const [query, setQuery] = useState('')
  const [provider, setProvider] = useState<string>('all')

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: qk.applications({ page_size: 200 }),
    queryFn: () => applicationsApi.list({ page_size: 200 }),
  })

  const apps = useMemo(() => data?.applications ?? [], [data])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return apps.filter((app) => {
      if (provider !== 'all' && normalizeEnum(app.cloud_provider) !== provider) return false
      if (!q) return true
      return [app.application_name, app.description, app.application_owner, app.argocd_app_name]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(q))
    })
  }, [apps, query, provider])

  const providers = useMemo(() => {
    const set = new Set<string>()
    for (const app of apps) {
      const p = normalizeEnum(app.cloud_provider)
      if (p) set.add(p)
    }
    return Array.from(set).sort()
  }, [apps])

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="shrink-0 space-y-4 border-b border-line px-6 py-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-1">
            <SectionLabel className="text-brand-400">Registry</SectionLabel>
            <h1 className="text-xl font-semibold tracking-tight text-content">Services</h1>
            <p className="text-xs text-content-subtle">
              What the agent knows about. Grounding lives here — an unregistered service can&apos;t be
              diagnosed.
            </p>
            {/* A5: live tickers */}
            <div className="flex items-center gap-4 pt-1 text-xs text-content-subtle">
              <span className="inline-flex items-center gap-1.5">
                <Boxes className="h-3.5 w-3.5 text-brand-400/80" aria-hidden />
                <CountUp to={apps.length} active={!isLoading} className="font-semibold text-content" />
                services
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-ok" aria-hidden />
                <CountUp to={apps.filter((a) => String(a.status).toLowerCase() === 'active').length} active={!isLoading} className="font-semibold text-content" />
                active
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Orbit className="h-3.5 w-3.5 text-violet-400/80" aria-hidden />
                <CountUp to={providers.length} active={!isLoading} className="font-semibold text-content" />
                clouds
              </span>
            </div>
          </div>

          {canManage && (
            <Button variant="primary" size="sm" asChild>
              <Link to="/services/new">
                <Plus className="h-3.5 w-3.5" aria-hidden />
                Register service
              </Link>
            </Button>
          )}
        </div>

        {/* Filters — one row above the content */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[200px] flex-1 sm:max-w-xs">
            <label htmlFor="service-search" className="sr-only">
              Search services
            </label>
            <Input
              id="service-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, owner, repo…"
              className="h-8 text-xs"
              leadingIcon={<Search className="h-3.5 w-3.5" />}
            />
          </div>

          <div className="flex items-center gap-1">
            <label htmlFor="provider-filter" className="sr-only">
              Filter by cloud provider
            </label>
            <select
              id="provider-filter"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="h-8 rounded-md border border-line-strong bg-surface-sunken/60 px-2.5 text-xs text-content transition-colors focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-ring/50"
            >
              <option value="all">All providers</option>
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          {/* View switcher */}
          <div
            className="ml-auto flex items-center gap-1 rounded-lg border border-line bg-surface-sunken/60 p-1"
            role="group"
            aria-label="View mode"
          >
            {VIEWS.map((v) => {
              const Icon = v.icon
              const active = view === v.id
              return (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setView(v.id)}
                  aria-pressed={active}
                  className={cn(
                    'relative flex items-center gap-1.5 rounded px-2.5 py-1 text-2xs font-medium transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                    active ? 'text-content' : 'text-content-subtle hover:text-content-muted',
                  )}
                >
                  {active && (
                    <motion.span
                      layoutId="view-active"
                      className="absolute inset-0 rounded bg-surface-overlay"
                      transition={{ type: 'spring', stiffness: 500, damping: 38 }}
                      aria-hidden
                    />
                  )}
                  <Icon className="relative h-3.5 w-3.5" aria-hidden />
                  <span className="relative hidden sm:inline">{v.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        <p className="text-2xs text-content-subtle" aria-live="polite">
          {isLoading ? 'Loading…' : `${filtered.length} of ${apps.length} services`}
        </p>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : isError ? (
          <ErrorState
            title="Could not load the registry"
            message={(error as ApiError)?.message}
            onRetry={() => refetch()}
            retrying={isFetching}
          />
        ) : apps.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No services registered yet"
            description="The agent grounds every answer in this registry. Add your first service so it knows which cluster, repo and dashboard to look at."
            action={
              canManage ? (
                <Button variant="primary" size="sm" asChild>
                  <Link to="/services/new">
                    <Plus className="h-3.5 w-3.5" aria-hidden />
                    Register your first service
                  </Link>
                </Button>
              ) : (
                <p className="text-2xs text-content-subtle">
                  Ask a team lead or administrator to register one.
                </p>
              )
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No services match those filters"
            description="Try a different search term or clear the provider filter."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setQuery('')
                  setProvider('all')
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <AnimatePresence mode="wait">
            {view === 'topology' ? (
              <motion.div
                key="topology"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="relative h-full min-h-[480px]"
              >
                <CanvasBoundary
                  fallback={
                    <EmptyState
                      icon={Orbit}
                      title="3D view unavailable"
                      description="Your browser or graphics driver has WebGL disabled. The grid and list views show the same services."
                      action={
                        <Button variant="outline" size="sm" onClick={() => setView('grid')}>
                          Switch to grid
                        </Button>
                      }
                    />
                  }
                >
                  <Suspense
                    fallback={
                      <div className="flex h-full items-center justify-center">
                        <Skeleton className="h-64 w-64 rounded-full" />
                      </div>
                    }
                  >
                    <ServiceTopology
                      apps={filtered}
                      onSelect={(app) => navigate(`/services/${app.id}`)}
                      className="h-full w-full"
                    />
                  </Suspense>
                </CanvasBoundary>

                {/* Legend + affordance hint over the canvas */}
                <div className="pointer-events-none absolute bottom-4 left-4 space-y-2 rounded-lg border border-line bg-surface/80 px-3 py-2.5 backdrop-blur-md">
                  <SectionLabel>Orbit = provider</SectionLabel>
                  <ul className="space-y-1">
                    {[
                      { label: 'GCP', color: '#0599b3' },
                      { label: 'AWS', color: '#9567e4' },
                      { label: 'Azure', color: '#219c6f' },
                    ].map((item) => (
                      <li key={item.label} className="flex items-center gap-2 text-2xs text-content-muted">
                        <span
                          className="h-2 w-2 rounded-sm"
                          style={{ background: item.color }}
                          aria-hidden
                        />
                        {item.label}
                      </li>
                    ))}
                  </ul>
                  <p className="pt-1 text-[10px] text-content-subtle">
                    Node size = config completeness · drag to orbit · click to open
                  </p>
                </div>
              </motion.div>
            ) : view === 'grid' ? (
              <motion.div
                key="grid"
                variants={staggerContainer(0.04)}
                initial="initial"
                animate="animate"
                exit={{ opacity: 0 }}
                className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-3"
              >
                {filtered.map((app) => (
                  <ServiceCard key={app.id} app={app} />
                ))}
              </motion.div>
            ) : (
              <motion.div
                key="list"
                variants={staggerContainer(0.02)}
                initial="initial"
                animate="animate"
                exit={{ opacity: 0 }}
                className="p-6"
              >
                <Card className="overflow-hidden">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Registered services</caption>
                    <thead>
                      <tr className="border-b border-line bg-surface-sunken/40">
                        {['Service', 'Provider', 'Owner', 'Status', 'Updated'].map((h) => (
                          <th
                            key={h}
                            scope="col"
                            className="px-4 py-2.5 text-left text-2xs font-semibold uppercase tracking-wider text-content-subtle"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {filtered.map((app) => (
                        <motion.tr
                          key={app.id}
                          variants={staggerItem}
                          className="cursor-pointer transition-colors hover:bg-surface-raised/40"
                          onClick={() => navigate(`/services/${app.id}`)}
                        >
                          <td className="px-4 py-3">
                            <Link
                              to={`/services/${app.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-medium text-content hover:text-brand-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded"
                            >
                              {app.application_name}
                            </Link>
                            {app.description && (
                              <p className="mt-0.5 line-clamp-1 text-2xs text-content-subtle">
                                {app.description}
                              </p>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <CloudBadge
                              provider={(normalizeEnum(app.cloud_provider) || 'unknown') as CloudProvider}
                            />
                          </td>
                          <td className="px-4 py-3 text-xs text-content-muted">
                            {app.application_owner || '—'}
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge
                              status={(normalizeEnum(app.status) || 'unknown') as ServiceStatus}
                            />
                          </td>
                          <td className="px-4 py-3 font-mono text-2xs text-content-subtle">
                            {formatRelative(app.updated_at ?? app.created_at)}
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ Card view */

function ServiceCard({ app }: { app: Application }) {
  const provider = (normalizeEnum(app.cloud_provider) || 'unknown') as CloudProvider
  const status = (normalizeEnum(app.status) || 'unknown') as ServiceStatus

  const integrations = [
    { label: 'GitHub', on: Boolean(app.github_repo) },
    { label: 'ArgoCD', on: Boolean(app.argocd_app_name) },
    { label: 'Grafana', on: Boolean(app.grafana_dashboard) },
  ]

  return (
    <motion.div variants={staggerItem}>
      <Link to={`/services/${app.id}`} className="block focus-visible:outline-none">
        <GlowCard className="h-full p-5 focus-visible:ring-2 focus-visible:ring-ring/60">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-sm font-semibold text-content">{app.application_name}</h3>
              <p className="mt-0.5 truncate text-2xs text-content-subtle">
                {app.application_owner || 'No owner set'}
              </p>
            </div>
            <CloudBadge provider={provider} />
          </div>

          <p className="mb-4 line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-content-muted">
            {app.description || 'No description provided.'}
          </p>

          <div className="flex items-center justify-between gap-3">
            <ul className="flex items-center gap-1.5">
              {integrations.map((item) => (
                <li
                  key={item.label}
                  className={cn(
                    'rounded border px-1.5 py-0.5 font-mono text-[10px]',
                    item.on
                      ? 'border-ok/25 bg-ok/10 text-ok'
                      : 'border-line bg-surface-sunken text-content-subtle/60',
                  )}
                  title={item.on ? `${item.label} configured` : `${item.label} not configured`}
                >
                  {item.label}
                </li>
              ))}
            </ul>
            <StatusBadge status={status} />
          </div>
        </GlowCard>
      </Link>
    </motion.div>
  )
}
