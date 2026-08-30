import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { format, subDays } from 'date-fns'
import { ArrowRight, Boxes, MessageSquareCode, Siren, ThumbsUp } from 'lucide-react'
import { applicationsApi, chatApi, feedbackApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { useAuth } from '@/lib/auth/AuthProvider'
import { GlowCard, CardBody, CardHeader, CardTitle, SectionLabel } from '@/components/ui/primitives'
import { Button } from '@/components/ui/Button'
import { Skeleton, SkeletonCard } from '@/components/ui/Skeleton'
import { EmptyState } from '@/components/ui/EmptyState'
import { CloudBadge, type CloudProvider } from '@/components/ui/Badge'
import {
  AXIS_PROPS,
  CHART_COLORS,
  ChartLegend,
  ChartTooltip,
  StackedShareBar,
} from '@/components/charts/primitives'
import { cn, formatRelative, normalizeEnum } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'
import { useEffect } from 'react'

/* ------------------------------------------------------- Animated number */

function Ticker({ value, className }: { value: number; className?: string }) {
  const motionValue = useMotionValue(0)
  const spring = useSpring(motionValue, { stiffness: 90, damping: 20 })
  const rounded = useTransform(spring, (v) => Math.round(v).toLocaleString())

  useEffect(() => {
    motionValue.set(value)
  }, [value, motionValue])

  // `tnum` keeps digit widths fixed so the number doesn't jitter as it counts.
  return <motion.span className={cn('tnum', className)}>{rounded}</motion.span>
}

/* ------------------------------------------------------------- Stat tile */

function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  accent = 'brand',
  loading,
}: {
  label: string
  value: number
  hint?: string
  icon: React.ElementType
  accent?: 'brand' | 'ok' | 'warn' | 'accent'
  loading?: boolean
}) {
  const accentHex = { brand: '#06b6d4', ok: '#22c55e', warn: '#f59e0b', accent: '#8b5cf6' }[accent]
  const iconClass = {
    brand: 'text-brand-300 bg-brand-500/10 ring-brand-500/20',
    ok: 'text-ok bg-ok/10 ring-ok/20',
    warn: 'text-warn bg-warn/10 ring-warn/20',
    accent: 'text-accent bg-accent/10 ring-accent/20',
  }[accent]

  return (
    <motion.div variants={staggerItem}>
      <GlowCard accent={accentHex} className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <SectionLabel>{label}</SectionLabel>
            {loading ? (
              <Skeleton className="h-9 w-20" />
            ) : (
              <p className="text-3xl font-semibold tracking-tight text-content">
                <Ticker value={value} />
              </p>
            )}
            {hint && <p className="truncate text-2xs text-content-subtle">{hint}</p>}
          </div>
          <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1', iconClass)}>
            <Icon className="h-4.5 w-4.5" aria-hidden />
          </div>
        </div>
      </GlowCard>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ Page */

export default function DashboardPage() {
  const { user, canManage } = useAuth()

  const results = useQueries({
    queries: [
      { queryKey: qk.sessions, queryFn: () => chatApi.listSessions(true) },
      { queryKey: qk.chatStats, queryFn: chatApi.stats },
      { queryKey: qk.applications({ page_size: 200 }), queryFn: () => applicationsApi.list({ page_size: 200 }) },
      { queryKey: qk.feedbackMine, queryFn: () => feedbackApi.mine(100) },
      {
        queryKey: qk.applicationStats,
        queryFn: applicationsApi.stats,
        enabled: canManage,
        retry: false,
      },
    ],
  })

  const [sessionsQ, chatStatsQ, appsQ, feedbackQ] = results
  const loading = results.some((r) => r.isLoading)

  const sessions = sessionsQ.data?.sessions ?? []
  const apps = useMemo(() => appsQ.data?.applications ?? [], [appsQ.data])
  const feedback = useMemo(() => feedbackQ.data ?? [], [feedbackQ.data])

  /* --------------------------------------------------- Derived series */

  // Service status — this is STATE, so it uses the reserved status palette,
  // never the categorical ramp.
  const statusSegments = useMemo(() => {
    const counts = { active: 0, inactive: 0, other: 0 }
    for (const app of apps) {
      const s = normalizeEnum(app.status)
      if (s === 'active') counts.active += 1
      else if (s === 'inactive') counts.inactive += 1
      else counts.other += 1
    }
    return [
      { label: 'Active', value: counts.active, color: CHART_COLORS.ok },
      { label: 'Inactive', value: counts.inactive, color: CHART_COLORS.neutral },
      { label: 'Other', value: counts.other, color: CHART_COLORS.warn },
    ].filter((s) => s.value > 0 || s.label !== 'Other')
  }, [apps])

  // Cloud mix — identity across three providers, so categorical hues in fixed
  // order. Colour follows the provider, never its rank, so filtering the list
  // never repaints the survivors.
  const cloudMix = useMemo(() => {
    const order: CloudProvider[] = ['gcp', 'aws', 'azure']
    const counts = new Map<string, number>()
    for (const app of apps) {
      const p = normalizeEnum(app.cloud_provider) || 'unknown'
      counts.set(p, (counts.get(p) ?? 0) + 1)
    }
    return order
      .map((provider, index) => ({
        provider,
        label: provider.toUpperCase(),
        count: counts.get(provider) ?? 0,
        color: CHART_COLORS.series[index],
      }))
      .filter((d) => d.count > 0)
  }, [apps])

  // Feedback over the last 14 days, bucketed by day.
  const feedbackTrend = useMemo(() => {
    const days = Array.from({ length: 14 }, (_, i) => subDays(new Date(), 13 - i))
    const buckets = days.map((day) => ({
      day: format(day, 'd MMM'),
      key: format(day, 'yyyy-MM-dd'),
      helpful: 0,
      unhelpful: 0,
    }))
    const index = new Map(buckets.map((b) => [b.key, b]))

    for (const item of feedback) {
      const created = item.created_at ? new Date(item.created_at) : null
      if (!created || Number.isNaN(created.getTime())) continue
      const bucket = index.get(format(created, 'yyyy-MM-dd'))
      if (!bucket) continue
      if (item.feedback_type === 'THUMBS_UP') bucket.helpful += 1
      else if (item.feedback_type === 'THUMBS_DOWN') bucket.unhelpful += 1
    }
    return buckets
  }, [feedback])

  const hasFeedback = feedbackTrend.some((d) => d.helpful > 0 || d.unhelpful > 0)
  const totalApps = apps.length
  const activeApps = statusSegments.find((s) => s.label === 'Active')?.value ?? 0

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <motion.div
        variants={staggerContainer(0.05)}
        initial="initial"
        animate="animate"
        className="mx-auto max-w-7xl space-y-6 p-6"
      >
        {/* Header */}
        <motion.header
          variants={staggerItem}
          className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] px-5 py-4 backdrop-blur-sm"
        >
          <div className="space-y-1">
            <SectionLabel className="text-brand-400">Mission control</SectionLabel>
            <h1 className="text-2xl font-semibold tracking-tight text-content">
              Welcome back, {user?.full_name?.split(' ')[0] || user?.username}
            </h1>
          </div>
          <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
            <Button variant="primary" size="sm" asChild>
              <Link to="/console">
                <MessageSquareCode className="h-3.5 w-3.5" aria-hidden />
                Open console
              </Link>
            </Button>
          </motion.div>
        </motion.header>

        {/* Stat row — hero numbers, no chart needed */}
        <motion.div variants={staggerContainer(0.05)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Registered services"
            value={totalApps}
            hint={`${activeApps} active`}
            icon={Boxes}
            accent="brand"
            loading={loading}
          />
          <StatTile
            label="Investigations"
            value={chatStatsQ.data?.total_sessions ?? sessions.length}
            hint={`${chatStatsQ.data?.sessions_created_today ?? 0} started today`}
            icon={MessageSquareCode}
            accent="accent"
            loading={loading}
          />
          <StatTile
            label="Messages exchanged"
            value={chatStatsQ.data?.total_messages ?? 0}
            hint="Across all sessions"
            icon={Siren}
            accent="warn"
            loading={loading}
          />
          <StatTile
            label="Feedback given"
            value={feedback.length}
            hint="Your contributions"
            icon={ThumbsUp}
            accent="ok"
            loading={loading}
          />
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* ------------------------------------------ Feedback trend */}
          <motion.div variants={staggerItem} className="lg:col-span-2">
            <GlowCard accent="#22c55e" className="h-full">
              <CardHeader>
                <div className="space-y-0.5">
                  <CardTitle>Answer quality</CardTitle>
                  <p className="text-2xs text-content-subtle">
                    Your ratings over the last 14 days
                  </p>
                </div>
                <ChartLegend
                  items={[
                    { label: 'Helpful', color: CHART_COLORS.ok },
                    { label: 'Not helpful', color: CHART_COLORS.danger },
                  ]}
                />
              </CardHeader>
              <CardBody>
                {loading ? (
                  <Skeleton className="h-52 w-full" />
                ) : !hasFeedback ? (
                  <EmptyState
                    size="sm"
                    icon={ThumbsUp}
                    title="No ratings yet"
                    description="Rate the agent's answers in the console and the trend will appear here."
                  />
                ) : (
                  <div className="h-52">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={feedbackTrend} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                        <defs>
                          <linearGradient id="fillHelpful" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={CHART_COLORS.ok} stopOpacity={0.28} />
                            <stop offset="100%" stopColor={CHART_COLORS.ok} stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="fillUnhelpful" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={CHART_COLORS.danger} stopOpacity={0.24} />
                            <stop offset="100%" stopColor={CHART_COLORS.danger} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        {/* Recessive grid: horizontal only, no vertical clutter. */}
                        <CartesianGrid
                          stroke={CHART_COLORS.grid}
                          strokeDasharray="3 3"
                          vertical={false}
                        />
                        <XAxis dataKey="day" {...AXIS_PROPS} interval="preserveStartEnd" minTickGap={24} />
                        <YAxis {...AXIS_PROPS} allowDecimals={false} width={32} />
                        <RTooltip
                          content={<ChartTooltip />}
                          cursor={{ stroke: CHART_COLORS.grid, strokeWidth: 1 }}
                        />
                        <Area
                          type="monotone"
                          dataKey="helpful"
                          name="Helpful"
                          stroke={CHART_COLORS.ok}
                          strokeWidth={2}
                          fill="url(#fillHelpful)"
                          dot={false}
                          activeDot={{ r: 4, strokeWidth: 2, stroke: CHART_COLORS.surface }}
                        />
                        <Area
                          type="monotone"
                          dataKey="unhelpful"
                          name="Not helpful"
                          stroke={CHART_COLORS.danger}
                          strokeWidth={2}
                          fill="url(#fillUnhelpful)"
                          dot={false}
                          activeDot={{ r: 4, strokeWidth: 2, stroke: CHART_COLORS.surface }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardBody>
            </GlowCard>
          </motion.div>

          {/* --------------------------------------------- Fleet status */}
          <motion.div variants={staggerItem}>
            <GlowCard accent="#8b5cf6" className="h-full">
              <CardHeader>
                <div className="space-y-0.5">
                  <CardTitle>Fleet status</CardTitle>
                  <p className="text-2xs text-content-subtle">Registry health</p>
                </div>
              </CardHeader>
              <CardBody className="space-y-5">
                {loading ? (
                  <Skeleton className="h-32 w-full" />
                ) : totalApps === 0 ? (
                  <EmptyState
                    size="sm"
                    icon={Boxes}
                    title="Nothing registered"
                    description="Register a service so the agent has something to ground its answers in."
                    action={
                      canManage ? (
                        <Button size="sm" variant="outline" asChild>
                          <Link to="/services/new">Register a service</Link>
                        </Button>
                      ) : undefined
                    }
                  />
                ) : (
                  <>
                    <div className="space-y-3">
                      <StackedShareBar segments={statusSegments} height={10} />
                      <ChartLegend
                        items={statusSegments.map((s) => ({
                          label: s.label,
                          color: s.color,
                          value: s.value,
                        }))}
                      />
                    </div>

                    <div className="rule-fade" />

                    <div className="space-y-2.5">
                      <SectionLabel>Cloud distribution</SectionLabel>
                      {cloudMix.length === 0 ? (
                        <p className="text-2xs text-content-subtle">No provider set.</p>
                      ) : (
                        <div className="h-[104px]">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                              data={cloudMix}
                              layout="vertical"
                              margin={{ top: 0, right: 28, bottom: 0, left: 0 }}
                              barCategoryGap={8}
                            >
                              <XAxis type="number" hide allowDecimals={false} />
                              <YAxis
                                type="category"
                                dataKey="label"
                                {...AXIS_PROPS}
                                width={48}
                                fontSize={11}
                              />
                              <RTooltip
                                content={<ChartTooltip />}
                                cursor={{ fill: 'hsl(var(--surface-raised) / 0.5)' }}
                              />
                              {/* 4px rounded data-end, anchored to the baseline. */}
                              <Bar dataKey="count" name="Services" radius={[0, 4, 4, 0]} barSize={14}>
                                {cloudMix.map((entry) => (
                                  <Cell key={entry.provider} fill={entry.color} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardBody>
            </GlowCard>
          </motion.div>
        </div>

        {/* Recent investigations */}
        <motion.div variants={staggerItem}>
          <GlowCard accent="#06b6d4">
            <CardHeader>
              <CardTitle>Recent investigations</CardTitle>
              <Button variant="ghost" size="xs" asChild>
                <Link to="/console">
                  View all
                  <ArrowRight className="h-3 w-3" aria-hidden />
                </Link>
              </Button>
            </CardHeader>
            <CardBody>
              {loading ? (
                <div className="space-y-2">
                  <SkeletonCard />
                </div>
              ) : sessions.length === 0 ? (
                <EmptyState
                  size="sm"
                  icon={MessageSquareCode}
                  title="No investigations yet"
                  description="Open the console and describe a symptom to get started."
                  action={
                    <Button size="sm" variant="outline" asChild>
                      <Link to="/console">Open console</Link>
                    </Button>
                  }
                />
              ) : (
                <ul className="divide-y divide-line">
                  {sessions.slice(0, 5).map((session) => (
                    <li key={session.id}>
                      <Link
                        to={`/console/${session.id}`}
                        className="group flex items-center gap-4 py-3 transition-colors hover:bg-surface-raised/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-lg px-2 -mx-2"
                      >
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-500/10 ring-1 ring-brand-500/20">
                          <MessageSquareCode className="h-3.5 w-3.5 text-brand-300" aria-hidden />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-content group-hover:text-brand-200">
                            {session.name || 'Untitled'}
                          </p>
                          <p className="font-mono text-2xs text-content-subtle">
                            {session.message_count ?? 0} messages · {formatRelative(session.last_modified)}
                          </p>
                        </div>
                        <ArrowRight
                          className="h-4 w-4 shrink-0 text-content-subtle opacity-0 transition-opacity group-hover:opacity-100"
                          aria-hidden
                        />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </GlowCard>
        </motion.div>

        {/* Services quick view */}
        {apps.length > 0 && (
          <motion.div variants={staggerItem}>
            <GlowCard accent="#8b5cf6">
              <CardHeader>
                <CardTitle>Registry</CardTitle>
                <Button variant="ghost" size="xs" asChild>
                  <Link to="/services">
                    All services
                    <ArrowRight className="h-3 w-3" aria-hidden />
                  </Link>
                </Button>
              </CardHeader>
              <CardBody>
                <div className="flex flex-wrap gap-2">
                  {apps.slice(0, 12).map((app) => (
                    <Link
                      key={app.id}
                      to={`/services/${app.id}`}
                      className="group flex items-center gap-2 rounded-lg border border-line bg-surface-sunken/60 px-3 py-2 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                    >
                      <span className="text-xs font-medium text-content-muted group-hover:text-content">
                        {app.application_name}
                      </span>
                      <CloudBadge
                        provider={(normalizeEnum(app.cloud_provider) || 'unknown') as CloudProvider}
                      />
                    </Link>
                  ))}
                </div>
              </CardBody>
            </GlowCard>
          </motion.div>
        )}
      </motion.div>
    </div>
  )
}
