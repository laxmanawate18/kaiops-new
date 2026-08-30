import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  Copy,
  ExternalLink,
  MessageSquareCode,
  Pencil,
  Power,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { applicationsApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { ApiError } from '@/lib/api/client'
import { useAuth } from '@/lib/auth/AuthProvider'
import { Button } from '@/components/ui/Button'
import { GlowCard, CardBody, CardHeader, CardTitle, SectionLabel, Tooltip } from '@/components/ui/primitives'
import { CloudBadge, StatusBadge, type CloudProvider, type ServiceStatus } from '@/components/ui/Badge'
import { ConfirmDialog } from '@/components/ui/Dialog'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { cn, formatDateTime, normalizeEnum } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'

/** Build an external link, or null when the base isn't configured. */
function externalUrl(kind: 'github' | 'grafana' | 'argocd', value?: string | null): string | null {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null

  // Only ever accept an absolute http(s) URL verbatim — this rejects
  // `javascript:` and other schemes outright.
  if (/^https?:\/\//i.test(trimmed)) {
    // A repo value ending in ".git" deep-links to an odd GitHub page; strip it.
    return kind === 'github' ? trimmed.replace(/\.git\/?$/i, '') : trimmed
  }

  const bases: Record<typeof kind, string | undefined> = {
    github: import.meta.env.VITE_GITHUB_URL || 'https://github.com',
    grafana: import.meta.env.VITE_GRAFANA_URL,
    argocd: import.meta.env.VITE_ARGOCD_URL,
  }
  const base = bases[kind]
  if (!base) return null

  const clean = base.replace(/\/$/, '')
  if (kind === 'github') return `${clean}/${trimmed.replace(/^\//, '')}`
  if (kind === 'grafana') return `${clean}/d/${encodeURIComponent(trimmed)}`
  return `${clean}/applications/${encodeURIComponent(trimmed)}`
}

function CopyableField({ label, value }: { label: string; value?: string | null }) {
  const [copied, setCopied] = useState(false)
  const display = value?.trim() || '—'
  const canCopy = Boolean(value?.trim())

  return (
    <div className="min-w-0 space-y-1">
      <SectionLabel>{label}</SectionLabel>
      <div className="group flex items-center gap-1.5">
        <p className="min-w-0 truncate font-mono text-xs text-content-muted" title={display}>
          {display}
        </p>
        {canCopy && (
          <button
            type="button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(value as string)
                setCopied(true)
                setTimeout(() => setCopied(false), 1500)
              } catch {
                toast.error('Clipboard blocked')
              }
            }}
            aria-label={`Copy ${label}`}
            className="shrink-0 rounded p-1 text-content-subtle opacity-0 transition-all group-hover:opacity-100 hover:bg-surface-overlay hover:text-content focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <Copy className={cn('h-3 w-3', copied && 'text-ok')} aria-hidden />
          </button>
        )}
      </div>
    </div>
  )
}

export default function ServiceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { canManage, isAdmin } = useAuth()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: app, isLoading, isError, error, refetch } = useQuery({
    queryKey: qk.application(id ?? ''),
    queryFn: () => applicationsApi.get(id as string),
    enabled: Boolean(id),
  })

  const toggle = useMutation({
    mutationFn: () => applicationsApi.toggleStatus(id as string),
    onSuccess: (updated) => {
      queryClient.setQueryData(qk.application(id as string), updated)
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      toast.success(`Service ${normalizeEnum(updated.status) === 'active' ? 'activated' : 'deactivated'}`)
    },
    onError: (e: ApiError) => toast.error('Could not change status', { description: e.message }),
  })

  const remove = useMutation({
    mutationFn: () => applicationsApi.remove(id as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      toast.success('Service deleted')
      navigate('/services')
    },
    onError: (e: ApiError) => toast.error('Could not delete', { description: e.message }),
  })

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-56 w-full rounded-xl" />
      </div>
    )
  }

  if (isError || !app) {
    return (
      <ErrorState
        title="Could not load that service"
        message={(error as ApiError)?.message ?? 'It may have been deleted.'}
        onRetry={() => refetch()}
      />
    )
  }

  const provider = (normalizeEnum(app.cloud_provider) || 'unknown') as CloudProvider
  const status = (normalizeEnum(app.status) || 'unknown') as ServiceStatus
  const isActive = status === 'active'

  const links = [
    { label: 'Repository', value: app.github_repo, href: externalUrl('github', app.github_repo) },
    { label: 'Dashboard', value: app.grafana_dashboard, href: externalUrl('grafana', app.grafana_dashboard) },
    { label: 'ArgoCD', value: app.argocd_app_name, href: externalUrl('argocd', app.argocd_app_name) },
  ]

  const workload: { label: string; value?: string | null }[] =
    provider === 'aws'
      ? [
          { label: 'Account ID', value: app.aws_account_id },
          { label: 'EKS cluster', value: app.eks_cluster_name },
          { label: 'Namespace', value: app.aws_namespace },
          { label: 'Deployment', value: app.aws_deployment_name },
          { label: 'Log group', value: app.cloudwatch_log_group_path },
          { label: 'Region', value: app.aws_region },
        ]
      : provider === 'azure'
        ? [
            { label: 'Subscription', value: app.azure_subscription_id },
            { label: 'AKS cluster', value: app.aks_cluster_name },
            { label: 'Namespace', value: app.azure_namespace },
            { label: 'Deployment', value: app.azure_deployment_name },
            { label: 'Resource group', value: app.resource_group },
            { label: 'Workspace', value: app.workspace },
          ]
        : [
            { label: 'Project ID', value: app.gcp_project_id },
            { label: 'GKE cluster', value: app.gke_cluster_name },
            { label: 'Namespace', value: app.namespace },
            { label: 'Deployment', value: app.deployment_name },
            { label: 'Pod prefix', value: app.pod_name },
            { label: 'Log resource', value: app.gcp_log_resource },
          ]

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <motion.div
        variants={staggerContainer(0.05)}
        initial="initial"
        animate="animate"
        className="mx-auto max-w-4xl space-y-6 p-6"
      >
        {/* Header */}
        <motion.div variants={staggerItem} className="space-y-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5 backdrop-blur-sm">
          <Button variant="ghost" size="xs" asChild className="-ml-2">
            <Link to="/services">
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              All services
            </Link>
          </Button>

          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-semibold tracking-tight text-content">
                  {app.application_name}
                </h1>
                <CloudBadge provider={provider} />
                <StatusBadge status={status} />
              </div>
              <p className="max-w-2xl text-pretty text-sm leading-relaxed text-content-muted">
                {app.description || 'No description provided.'}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.97 }}>
                <Button variant="primary" size="sm" asChild>
                  <Link
                    to="/console"
                    state={{}}
                    onClick={() => {
                      sessionStorage.setItem(
                        'kaiops.seedPrompt',
                        `Run a root cause analysis for ${app.application_name}.`,
                      )
                    }}
                  >
                    <MessageSquareCode className="h-3.5 w-3.5" aria-hidden />
                    Investigate
                  </Link>
                </Button>
              </motion.div>

              {canManage && (
                <>
                  <Button variant="outline" size="sm" asChild>
                    <Link to={`/services/${app.id}/edit`}>
                      <Pencil className="h-3.5 w-3.5" aria-hidden />
                      Edit
                    </Link>
                  </Button>
                  <Tooltip content={isActive ? 'Deactivate' : 'Activate'}>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      loading={toggle.isPending}
                      onClick={() => toggle.mutate()}
                      aria-label={isActive ? 'Deactivate service' : 'Activate service'}
                    >
                      {!toggle.isPending && <Power className="h-3.5 w-3.5" aria-hidden />}
                    </Button>
                  </Tooltip>
                </>
              )}

              {isAdmin && (
                <Tooltip content="Delete service">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setConfirmDelete(true)}
                    aria-label="Delete service"
                    className="text-danger hover:bg-danger/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>
        </motion.div>

        {/* Integrations */}
        <motion.div variants={staggerItem}>
          <GlowCard accent="#8b5cf6">
            <CardHeader>
              <CardTitle>Integrations</CardTitle>
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-3">
              {links.map((link) => (
                <div key={link.label} className="min-w-0 space-y-1">
                  <SectionLabel>{link.label}</SectionLabel>
                  {link.value ? (
                    link.href ? (
                      <a
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex min-w-0 items-center gap-1 font-mono text-xs text-brand-300 transition-colors hover:text-brand-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded"
                      >
                        <span className="truncate">{link.value}</span>
                        <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
                      </a>
                    ) : (
                      <Tooltip content="Set the matching VITE_*_URL to enable a deep link">
                        <p className="truncate font-mono text-xs text-content-muted">{link.value}</p>
                      </Tooltip>
                    )
                  ) : (
                    <p className="font-mono text-xs text-content-subtle">Not configured</p>
                  )}
                </div>
              ))}
            </CardBody>
          </GlowCard>
        </motion.div>

        {/* Workload */}
        <motion.div variants={staggerItem}>
          <GlowCard accent="#06b6d4">
            <CardHeader>
              <div className="space-y-0.5">
                <CardTitle>Workload</CardTitle>
                <p className="text-2xs text-content-subtle">
                  Where the agent looks for logs and events on {provider.toUpperCase()}.
                </p>
              </div>
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-3">
              {workload.map((field) => (
                <CopyableField key={field.label} label={field.label} value={field.value} />
              ))}
            </CardBody>
          </GlowCard>
        </motion.div>

        {/* Ingress + meta */}
        <motion.div variants={staggerItem} className="grid gap-6 sm:grid-cols-2">
          <GlowCard accent="#22c55e">
            <CardHeader>
              <CardTitle>Ingress</CardTitle>
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <CopyableField label="Name" value={app.ingress_name} />
              <CopyableField label="Public IP" value={app.ingress_public_ip} />
              <CopyableField label="Namespace" value={app.ingress_namespace} />
            </CardBody>
          </GlowCard>

          <GlowCard accent="#f59e0b">
            <CardHeader>
              <CardTitle>Record</CardTitle>
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1">
                <SectionLabel>Owner</SectionLabel>
                <p className="text-xs text-content-muted">{app.application_owner || '—'}</p>
              </div>
              <div className="space-y-1">
                <SectionLabel>Criticality</SectionLabel>
                <p className="text-xs capitalize text-content-muted">
                  {app.application_criticality || '—'}
                </p>
              </div>
              <div className="space-y-1">
                <SectionLabel>Created</SectionLabel>
                <p className="text-xs text-content-muted">{formatDateTime(app.created_at)}</p>
              </div>
              <div className="space-y-1">
                <SectionLabel>Updated</SectionLabel>
                <p className="text-xs text-content-muted">{formatDateTime(app.updated_at)}</p>
              </div>
              <div className="space-y-1 sm:col-span-2">
                <CopyableField label="Service ID" value={app.id} />
              </div>
            </CardBody>
          </GlowCard>
        </motion.div>
      </motion.div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        title={`Delete ${app.application_name}?`}
        description="The agent will lose all grounding for this service and can no longer diagnose it. This cannot be undone."
        confirmText="Delete service"
        tone="danger"
      />
    </div>
  )
}
