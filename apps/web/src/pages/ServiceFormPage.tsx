import { useEffect, useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { ArrowLeft, Cloud, GitBranch, Info, Server } from 'lucide-react'
import { toast } from 'sonner'
import { applicationsApi } from '@/lib/api/endpoints'
import { qk } from '@/lib/queryClient'
import { ApiError } from '@/lib/api/client'
import type { Application } from '@/lib/api/types'
import { Button } from '@/components/ui/Button'
import { TextField, Field, Textarea } from '@/components/ui/Input'
import { Card, CardBody, CardHeader, CardTitle, SectionLabel } from '@/components/ui/primitives'
import { Skeleton } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/EmptyState'
import { cn, normalizeEnum } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/motion'

/**
 * Validation mirrors the server's Pydantic validators exactly
 * (`app/applications/models.py`), including the conditional cloud-provider
 * requirements. Anything the server would reject, we reject inline first —
 * a surprise 422 after filling in 30 fields is a miserable experience.
 */
const base = {
  application_name: z
    .string()
    .min(2, 'At least 2 characters')
    .max(100, 'At most 100 characters')
    .regex(/^[A-Za-z0-9\s_-]+$/, 'Letters, numbers, spaces, underscore and hyphen only'),
  application_owner: z.string().min(1, 'Who owns this service?'),
  github_repo: z.string().optional().or(z.literal('')),
  argocd_app_name: z.string().max(100, 'At most 100 characters').optional().or(z.literal('')),
  grafana_dashboard: z.string().optional().or(z.literal('')),
  description: z.string().max(500, 'At most 500 characters').optional().or(z.literal('')),
  application_criticality: z.string().optional(),
  status: z.enum(['active', 'inactive', 'pending', 'suspended']).default('active'),
  cloud_provider: z.enum(['gcp', 'aws', 'azure']).default('gcp'),
}

const schema = z
  .object({
    ...base,
    // GCP
    gcp_project_id: z.string().optional().or(z.literal('')),
    gke_cluster_name: z.string().optional().or(z.literal('')),
    namespace: z.string().optional().or(z.literal('')),
    gcp_log_resource: z.string().optional().or(z.literal('')),
    deployment_name: z.string().optional().or(z.literal('')),
    pod_name: z.string().optional().or(z.literal('')),
    // Azure
    azure_subscription_id: z.string().optional().or(z.literal('')),
    aks_cluster_name: z.string().optional().or(z.literal('')),
    azure_namespace: z.string().optional().or(z.literal('')),
    azure_deployment_name: z.string().optional().or(z.literal('')),
    resource_group: z.string().optional().or(z.literal('')),
    workspace: z.string().optional().or(z.literal('')),
    // AWS
    aws_account_id: z.string().optional().or(z.literal('')),
    eks_cluster_name: z.string().optional().or(z.literal('')),
    aws_namespace: z.string().optional().or(z.literal('')),
    aws_deployment_name: z.string().optional().or(z.literal('')),
    cloudwatch_log_group_path: z.string().optional().or(z.literal('')),
    // Ingress
    ingress_name: z.string().optional().or(z.literal('')),
    ingress_public_ip: z.string().optional().or(z.literal('')),
    ingress_namespace: z.string().optional().or(z.literal('')),
  })
  .superRefine((data, ctx) => {
    const req = (field: keyof typeof data, message: string) => {
      if (!data[field] || String(data[field]).trim() === '') {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: [field], message })
      }
    }

    if (data.cloud_provider === 'gcp') {
      req('gcp_project_id', 'Required for GCP')
      req('gke_cluster_name', 'Required for GCP')
      req('namespace', 'Required for GCP')
      if (data.gcp_project_id && !/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(data.gcp_project_id)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['gcp_project_id'],
          message: '6–30 chars, lowercase, must start with a letter',
        })
      }
      if (data.gke_cluster_name && !/^[a-z][a-z0-9-]*[a-z0-9]$/.test(data.gke_cluster_name)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['gke_cluster_name'],
          message: 'Lowercase letters, numbers and hyphens',
        })
      }
      if (data.namespace && !/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(data.namespace)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['namespace'],
          message: 'Lowercase letters, numbers and hyphens',
        })
      }
    }

    if (data.cloud_provider === 'azure') {
      req('azure_subscription_id', 'Required for Azure')
      if (
        data.azure_subscription_id &&
        !/^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/.test(
          data.azure_subscription_id,
        )
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['azure_subscription_id'],
          message: 'Must be a UUID',
        })
      }
    }

    if (data.cloud_provider === 'aws') {
      req('aws_account_id', 'Required for AWS')
      if (data.aws_account_id && !/^\d{12}$/.test(data.aws_account_id)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['aws_account_id'],
          message: 'Exactly 12 digits',
        })
      }
    }
  })

type FormValues = z.infer<typeof schema>

export default function ServiceFormPage() {
  const { id } = useParams<{ id: string }>()
  // Legacy create slugs still routed here ("/services/register", "/services/new",
  // "/services/create") match the :id route — never treat them as edit ids,
  // that fired doomed GET /applications/<slug> 404s.
  const CREATE_SLUGS = ['new', 'register', 'create']
  const isCreateSlug = !id || CREATE_SLUGS.includes(id)
  const isEdit = Boolean(id) && !isCreateSlug
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const existing = useQuery({
    queryKey: qk.application(id ?? ''),
    queryFn: () => applicationsApi.get(id as string),
    enabled: isEdit,
  })

  const {
    register,
    handleSubmit,
    watch,
    reset,
    setError,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { status: 'active', cloud_provider: 'gcp' },
  })

  const provider = watch('cloud_provider')

  // Hydrate the form once the record arrives.
  useEffect(() => {
    if (!existing.data) return
    const app = existing.data
    reset({
      application_name: app.application_name ?? '',
      application_owner: app.application_owner ?? '',
      github_repo: app.github_repo ?? '',
      argocd_app_name: app.argocd_app_name ?? '',
      grafana_dashboard: app.grafana_dashboard ?? '',
      description: app.description ?? '',
      application_criticality: app.application_criticality ?? 'medium',
      status: (normalizeEnum(app.status) || 'active') as FormValues['status'],
      cloud_provider: (normalizeEnum(app.cloud_provider) || 'gcp') as FormValues['cloud_provider'],
      gcp_project_id: app.gcp_project_id ?? '',
      gke_cluster_name: app.gke_cluster_name ?? '',
      namespace: app.namespace ?? '',
      gcp_log_resource: app.gcp_log_resource ?? '',
      deployment_name: app.deployment_name ?? '',
      pod_name: app.pod_name ?? '',
      azure_subscription_id: app.azure_subscription_id ?? '',
      aks_cluster_name: app.aks_cluster_name ?? '',
      azure_namespace: app.azure_namespace ?? '',
      azure_deployment_name: app.azure_deployment_name ?? '',
      resource_group: app.resource_group ?? '',
      workspace: app.workspace ?? '',
      aws_account_id: app.aws_account_id ?? '',
      eks_cluster_name: app.eks_cluster_name ?? '',
      aws_namespace: app.aws_namespace ?? '',
      aws_deployment_name: app.aws_deployment_name ?? '',
      cloudwatch_log_group_path: app.cloudwatch_log_group_path ?? '',
      ingress_name: app.ingress_name ?? '',
      ingress_public_ip: app.ingress_public_ip ?? '',
      ingress_namespace: app.ingress_namespace ?? '',
    })
  }, [existing.data, reset])

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      // Strip empty strings so we never write "" over a real value.
      const payload: Partial<Application> = {}
      for (const [key, value] of Object.entries(values)) {
        if (value !== '' && value !== undefined && value !== null) {
          ;(payload as Record<string, unknown>)[key] = value
        }
      }
      return isEdit ? applicationsApi.update(id as string, payload) : applicationsApi.create(payload)
    },
    onSuccess: (app) => {
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      toast.success(isEdit ? 'Service updated' : 'Service registered', {
        description: `${app.application_name} is now available to the agent.`,
      })
      navigate(`/services/${app.id}`)
    },
    onError: (error: ApiError) => {
      for (const [field, message] of Object.entries(error.fieldErrors)) {
        setError(field as keyof FormValues, { message })
      }
      toast.error(isEdit ? 'Could not save changes' : 'Could not register service', {
        description: error.message,
      })
    },
  })

  const onSubmit = handleSubmit(
    (values) => save.mutate(values),
    () => {
      // Scroll to the first invalid control — on a form this long the errors
      // are often far off-screen and the submit just looks dead.
      const firstError = document.querySelector('[aria-invalid="true"]')
      firstError?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      ;(firstError as HTMLElement | null)?.focus?.()
      toast.error('Some fields need attention')
    },
  )

  const providerFields = useMemo(() => {
    if (provider === 'aws') {
      return [
        { name: 'aws_account_id' as const, label: 'AWS account ID', required: true, placeholder: '123456789012', hint: 'Exactly 12 digits' },
        { name: 'eks_cluster_name' as const, label: 'EKS cluster', placeholder: 'prod-eks' },
        { name: 'aws_namespace' as const, label: 'Namespace', placeholder: 'default' },
        { name: 'aws_deployment_name' as const, label: 'Deployment', placeholder: 'payments' },
        { name: 'cloudwatch_log_group_path' as const, label: 'CloudWatch log group', placeholder: '/aws/containerinsights/prod-eks/application' },
      ]
    }
    if (provider === 'azure') {
      return [
        { name: 'azure_subscription_id' as const, label: 'Subscription ID', required: true, placeholder: '00000000-0000-0000-0000-000000000000', hint: 'UUID format' },
        { name: 'aks_cluster_name' as const, label: 'AKS cluster', placeholder: 'prod-aks' },
        { name: 'azure_namespace' as const, label: 'Namespace', placeholder: 'kaiops-ns' },
        { name: 'azure_deployment_name' as const, label: 'Deployment', placeholder: 'payments' },
        { name: 'resource_group' as const, label: 'Resource group', placeholder: 'rg-prod' },
        { name: 'workspace' as const, label: 'Log Analytics workspace', placeholder: 'law-prod' },
      ]
    }
    return [
      { name: 'gcp_project_id' as const, label: 'GCP project ID', required: true, placeholder: 'my-project-123', hint: '6–30 chars, lowercase' },
      { name: 'gke_cluster_name' as const, label: 'GKE cluster', required: true, placeholder: 'prod-gke' },
      { name: 'namespace' as const, label: 'Namespace', required: true, placeholder: 'default' },
      { name: 'gcp_log_resource' as const, label: 'Log resource', placeholder: 'k8s_container' },
      { name: 'deployment_name' as const, label: 'Deployment', placeholder: 'payments' },
      { name: 'pod_name' as const, label: 'Pod prefix', placeholder: 'payments-' },
    ]
  }, [provider])

  if (isEdit && existing.isLoading) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    )
  }

  if (isEdit && existing.isError) {
    return (
      <ErrorState
        title="Could not load that service"
        message={(existing.error as ApiError)?.message}
        onRetry={() => existing.refetch()}
      />
    )
  }

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <motion.form
        onSubmit={onSubmit}
        variants={staggerContainer(0.05)}
        initial="initial"
        animate="animate"
        className="mx-auto max-w-3xl space-y-6 p-6"
        noValidate
      >
        {/* Header */}
        <motion.div variants={staggerItem} className="space-y-3">
          <Button variant="ghost" size="xs" asChild className="-ml-2">
            <Link to={isEdit ? `/services/${id}` : '/services'}>
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
              Back
            </Link>
          </Button>
          <div className="space-y-1">
            <SectionLabel className="text-brand-400">Registry</SectionLabel>
            <h1 className="text-xl font-semibold tracking-tight text-content">
              {isEdit ? 'Edit service' : 'Register a service'}
            </h1>
            <p className="text-xs text-content-subtle">
              These fields are what the agent uses to find your logs, metrics and deploy state. The
              more you fill in, the better its answers.
            </p>
          </div>
        </motion.div>

        {/* Identity */}
        <motion.div variants={staggerItem}>
          <Card>
            <CardHeader>
              <CardTitle>Identity</CardTitle>
              <Server className="h-4 w-4 text-content-subtle" aria-hidden />
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Service name"
                required
                placeholder="payments-api"
                error={errors.application_name?.message}
                {...register('application_name')}
              />
              <TextField
                label="Owner"
                required
                placeholder="Platform team"
                error={errors.application_owner?.message}
                {...register('application_owner')}
              />

              <Field label="Description" htmlFor="description" className="sm:col-span-2">
                <Textarea
                  id="description"
                  rows={2}
                  maxLength={500}
                  placeholder="Handles card authorisation and settlement callbacks."
                  invalid={Boolean(errors.description)}
                  {...register('description')}
                />
              </Field>

              <Field label="Criticality" htmlFor="criticality">
                <select
                  id="criticality"
                  className="h-9.5 w-full rounded-md border border-line-strong bg-surface-sunken/60 px-3 text-sm text-content focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-ring/50"
                  {...register('application_criticality')}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </Field>

              <Field label="Status" htmlFor="status">
                <select
                  id="status"
                  className="h-9.5 w-full rounded-md border border-line-strong bg-surface-sunken/60 px-3 text-sm text-content focus:border-brand-500/50 focus:outline-none focus:ring-2 focus:ring-ring/50"
                  {...register('status')}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="pending">Pending</option>
                  <option value="suspended">Suspended</option>
                </select>
              </Field>
            </CardBody>
          </Card>
        </motion.div>

        {/* Integrations */}
        <motion.div variants={staggerItem}>
          <Card>
            <CardHeader>
              <div className="space-y-0.5">
                <CardTitle>Integrations</CardTitle>
              </div>
              <GitBranch className="h-4 w-4 text-content-subtle" aria-hidden />
            </CardHeader>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="GitHub repository"
                placeholder="acme/payments-api"
                hint="owner/repo or a full URL"
                error={errors.github_repo?.message}
                {...register('github_repo')}
              />
              <TextField
                label="ArgoCD application"
                placeholder="payments-api-prod"
                hint="Exact name in ArgoCD, not your service name"
                error={errors.argocd_app_name?.message}
                {...register('argocd_app_name')}
              />
              <TextField
                label="Grafana dashboard"
                placeholder="payments-overview"
                error={errors.grafana_dashboard?.message}
                className="sm:col-span-2"
                {...register('grafana_dashboard')}
              />
            </CardBody>
          </Card>
        </motion.div>

        {/* Cloud */}
        <motion.div variants={staggerItem}>
          <Card>
            <CardHeader>
              <div className="space-y-0.5">
                <CardTitle>Cloud &amp; workload</CardTitle>
                <p className="text-2xs text-content-subtle">
                  Required fields change with the provider.
                </p>
              </div>
              <Cloud className="h-4 w-4 text-content-subtle" aria-hidden />
            </CardHeader>
            <CardBody className="space-y-4">
              <Field label="Cloud provider" required>
                <div className="flex gap-2" role="radiogroup" aria-label="Cloud provider">
                  {(['gcp', 'aws', 'azure'] as const).map((p) => (
                    <label
                      key={p}
                      className={cn(
                        'flex flex-1 cursor-pointer items-center justify-center rounded-lg border px-3 py-2.5 text-xs font-medium transition-all',
                        'focus-within:ring-2 focus-within:ring-ring/60',
                        provider === p
                          ? 'border-brand-500/40 bg-brand-500/10 text-brand-200'
                          : 'border-line-strong bg-surface-sunken text-content-muted hover:text-content',
                      )}
                    >
                      <input
                        type="radio"
                        value={p}
                        className="sr-only"
                        {...register('cloud_provider')}
                      />
                      {p.toUpperCase()}
                    </label>
                  ))}
                </div>
              </Field>

              <motion.div
                key={provider}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="grid gap-4 sm:grid-cols-2"
              >
                {providerFields.map((field) => (
                  <TextField
                    key={field.name}
                    label={field.label}
                    required={'required' in field ? field.required : false}
                    placeholder={field.placeholder}
                    hint={'hint' in field ? field.hint : undefined}
                    error={errors[field.name]?.message}
                    {...register(field.name)}
                  />
                ))}
              </motion.div>

              <div className="rule-fade" />

              <div className="space-y-3">
                <SectionLabel>Ingress (optional)</SectionLabel>
                <div className="grid gap-4 sm:grid-cols-3">
                  <TextField label="Ingress name" placeholder="payments-ingress" {...register('ingress_name')} />
                  <TextField label="Public IP" placeholder="34.10.0.1" {...register('ingress_public_ip')} />
                  <TextField label="Namespace" placeholder="ingress-nginx" {...register('ingress_namespace')} />
                </div>
              </div>
            </CardBody>
          </Card>
        </motion.div>

        {/* Actions */}
        <motion.div
          variants={staggerItem}
          className="sticky bottom-0 -mx-6 flex items-center gap-3 border-t border-line bg-canvas/90 px-6 py-4 backdrop-blur-md"
        >
          <Button
            type="submit"
            variant="primary"
            loading={isSubmitting || save.isPending}
            disabled={isEdit && !isDirty}
          >
            {isEdit ? 'Save changes' : 'Register service'}
          </Button>
          <Button variant="ghost" asChild>
            <Link to={isEdit ? `/services/${id}` : '/services'}>Cancel</Link>
          </Button>

          <p className="ml-auto flex items-center gap-1.5 text-2xs text-content-subtle">
            <Info className="h-3 w-3" aria-hidden />
            Fields marked * are required
          </p>
        </motion.div>
      </motion.form>
    </div>
  )
}
