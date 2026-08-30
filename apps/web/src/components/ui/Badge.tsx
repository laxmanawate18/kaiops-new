import { cn } from '@/lib/utils'

type Tone = 'brand' | 'ok' | 'warn' | 'danger' | 'info' | 'neutral' | 'accent'

const TONES: Record<Tone, string> = {
  brand: 'bg-brand-500/12 text-brand-200 border-brand-500/25',
  ok: 'bg-ok/12 text-ok border-ok/25',
  warn: 'bg-warn/12 text-warn border-warn/25',
  danger: 'bg-danger/12 text-danger border-danger/30',
  info: 'bg-info/12 text-info border-info/25',
  neutral: 'bg-neutral/12 text-content-muted border-line-strong',
  accent: 'bg-accent/12 text-accent border-accent/25',
}

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  size?: 'sm' | 'md'
  /** Leading dot. Adds a non-colour cue is handled by the label itself. */
  dot?: boolean
  pulse?: boolean
}

export function Badge({
  tone = 'neutral',
  size = 'sm',
  dot,
  pulse,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium leading-none',
        size === 'sm' ? 'px-2 py-1 text-2xs' : 'px-2.5 py-1.5 text-xs',
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot && (
        <span className="relative flex h-1.5 w-1.5 shrink-0" aria-hidden>
          {pulse && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
          )}
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {children}
    </span>
  )
}

/* ------------------------------------------------------------ Status badge */

export type ServiceStatus = 'active' | 'inactive' | 'unknown'

const STATUS_META: Record<ServiceStatus, { tone: Tone; label: string }> = {
  active: { tone: 'ok', label: 'Active' },
  inactive: { tone: 'neutral', label: 'Inactive' },
  unknown: { tone: 'neutral', label: 'Unknown' },
}

/**
 * Status is conveyed by dot colour *and* a text label — colour alone would
 * fail for the ~8% of men with a colour-vision deficiency.
 */
export function StatusBadge({ status, className }: { status: ServiceStatus; className?: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.unknown
  return (
    <Badge tone={meta.tone} dot pulse={status === 'active'} className={className}>
      {meta.label}
    </Badge>
  )
}

/* ---------------------------------------------------------- Severity badge */

export type Severity = 'P0' | 'P1' | 'P2' | 'P3'

const SEVERITY_STYLES: Record<Severity, string> = {
  P0: 'bg-sev-p0/15 text-sev-p0 border-sev-p0/40',
  P1: 'bg-sev-p1/15 text-sev-p1 border-sev-p1/35',
  P2: 'bg-sev-p2/15 text-sev-p2 border-sev-p2/35',
  P3: 'bg-sev-p3/15 text-sev-p3 border-sev-p3/35',
}

export function SeverityBadge({
  severity,
  className,
  pulse,
}: {
  severity: Severity
  className?: string
  pulse?: boolean
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-2xs font-semibold tracking-wider',
        SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.P3,
        className,
      )}
    >
      <span className="relative flex h-1.5 w-1.5" aria-hidden>
        {pulse && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-70" />
        )}
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
      </span>
      {severity}
    </span>
  )
}

/* ------------------------------------------------------------ Cloud badge */

export type CloudProvider = 'gcp' | 'aws' | 'azure' | 'unknown'

const CLOUD_META: Record<CloudProvider, { label: string; className: string }> = {
  gcp: { label: 'GCP', className: 'bg-info/12 text-info border-info/25' },
  aws: { label: 'AWS', className: 'bg-warn/12 text-warn border-warn/25' },
  azure: { label: 'Azure', className: 'bg-brand-500/12 text-brand-200 border-brand-500/25' },
  unknown: { label: 'Unset', className: 'bg-neutral/12 text-content-subtle border-line-strong' },
}

export function CloudBadge({ provider, className }: { provider: CloudProvider; className?: string }) {
  const meta = CLOUD_META[provider] ?? CLOUD_META.unknown
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-2xs font-semibold tracking-wide',
        meta.className,
        className,
      )}
    >
      {meta.label}
    </span>
  )
}
