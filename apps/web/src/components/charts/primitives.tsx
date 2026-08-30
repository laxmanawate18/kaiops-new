import { cn } from '@/lib/utils'

/**
 * Shared chart furniture.
 *
 * Rules encoded here so no individual chart has to remember them:
 *  - text always wears text tokens, never the series colour
 *  - a legend is present whenever there are >= 2 series
 *  - grid and axes are recessive
 *  - every mark gets a hover tooltip
 */

export const CHART_COLORS = {
  series: [
    'hsl(var(--series-1))',
    'hsl(var(--series-2))',
    'hsl(var(--series-3))',
    'hsl(var(--series-4))',
    'hsl(var(--series-5))',
    'hsl(var(--series-6))',
    'hsl(var(--series-7))',
    'hsl(var(--series-8))',
  ],
  ok: 'hsl(var(--ok))',
  warn: 'hsl(var(--warn))',
  danger: 'hsl(var(--danger))',
  neutral: 'hsl(var(--neutral))',
  grid: 'hsl(var(--line))',
  axis: 'hsl(var(--content-subtle))',
  surface: 'hsl(var(--surface))',
} as const

export const AXIS_PROPS = {
  stroke: CHART_COLORS.axis,
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const

/** Tooltip shell matching the app's overlay surface. */
export function ChartTooltip({
  active,
  payload,
  label,
  valueFormatter,
}: {
  active?: boolean
  payload?: { name?: string; value?: number | string; color?: string; dataKey?: string }[]
  label?: string | number
  valueFormatter?: (value: number | string) => string
}) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-lg border border-line-strong bg-surface-overlay px-3 py-2 shadow-overlay">
      {label !== undefined && label !== '' && (
        <p className="mb-1.5 text-2xs font-medium text-content-muted">{label}</p>
      )}
      <ul className="space-y-1">
        {payload.map((entry, i) => (
          <li key={`${entry.dataKey}-${i}`} className="flex items-center gap-2 text-xs">
            <span
              className="h-2 w-2 shrink-0 rounded-sm"
              style={{ background: entry.color }}
              aria-hidden
            />
            <span className="text-content-muted">{entry.name}</span>
            <span className="ml-auto pl-3 font-mono tabular-nums text-content">
              {valueFormatter ? valueFormatter(entry.value ?? 0) : entry.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Legend. Identity is carried by a swatch *plus* a text label, so it never
 * depends on colour alone.
 */
export function ChartLegend({
  items,
  className,
}: {
  items: { label: string; color: string; value?: string | number }[]
  className?: string
}) {
  return (
    <ul className={cn('flex flex-wrap items-center gap-x-4 gap-y-1.5', className)}>
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-2xs">
          <span
            className="h-2 w-2 shrink-0 rounded-sm"
            style={{ background: item.color }}
            aria-hidden
          />
          <span className="text-content-muted">{item.label}</span>
          {item.value !== undefined && (
            <span className="font-mono tabular-nums text-content-subtle">{item.value}</span>
          )}
        </li>
      ))}
    </ul>
  )
}

/**
 * Part-to-whole as a single horizontal bar.
 *
 * Preferred over a donut for a handful of states: lengths on a common
 * baseline are far easier to compare than arc angles, and it costs a fraction
 * of the vertical space. A 2px surface-coloured gap separates segments.
 */
export function StackedShareBar({
  segments,
  className,
  height = 8,
}: {
  segments: { label: string; value: number; color: string }[]
  className?: string
  height?: number
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  if (total === 0) {
    return (
      <div
        className={cn('w-full rounded-full bg-surface-overlay', className)}
        style={{ height }}
        aria-hidden
      />
    )
  }

  return (
    <div
      className={cn('flex w-full overflow-hidden rounded-full bg-surface-overlay', className)}
      style={{ height, gap: 2 }}
      role="img"
      aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(', ')}
    >
      {segments
        .filter((s) => s.value > 0)
        .map((segment) => (
          <div
            key={segment.label}
            className="h-full rounded-full transition-all duration-500 ease-emphasis first:rounded-l-full last:rounded-r-full"
            style={{
              width: `${(segment.value / total) * 100}%`,
              background: segment.color,
            }}
            title={`${segment.label}: ${segment.value}`}
          />
        ))}
    </div>
  )
}
