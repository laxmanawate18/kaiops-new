import { forwardRef, useRef, useState } from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as SeparatorPrimitive from '@radix-ui/react-separator'
import * as AvatarPrimitive from '@radix-ui/react-avatar'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn, initials } from '@/lib/utils'

/* --------------------------------------------------------------- Tooltip */

export const TooltipProvider = TooltipPrimitive.Provider

export function Tooltip({
  content,
  children,
  side = 'top',
  align = 'center',
  delay = 250,
}: {
  content: React.ReactNode
  children: React.ReactNode
  side?: 'top' | 'right' | 'bottom' | 'left'
  align?: 'start' | 'center' | 'end'
  delay?: number
}) {
  if (!content) return <>{children}</>
  return (
    <TooltipPrimitive.Root delayDuration={delay}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          align={align}
          sideOffset={6}
          className={cn(
            'z-50 max-w-xs rounded-md border border-line-strong bg-surface-overlay px-2.5 py-1.5',
            'text-xs leading-relaxed text-content shadow-overlay',
            'data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0 data-[state=delayed-open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-surface-overlay" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

/* ------------------------------------------------------------------ Tabs */

export const Tabs = TabsPrimitive.Root

export const TabsList = forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(function TabsList({ className, ...props }, ref) {
  return (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        'inline-flex items-center gap-1 rounded-lg border border-line bg-surface-sunken/60 p-1',
        className,
      )}
      {...props}
    />
  )
})

export const TabsTrigger = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(function TabsTrigger({ className, ...props }, ref) {
  return (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        'relative rounded-md px-3 py-1.5 text-xs font-medium text-content-muted transition-colors',
        'hover:text-content',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        'data-[state=active]:bg-surface-overlay data-[state=active]:text-content data-[state=active]:shadow-subtle',
        className,
      )}
      {...props}
    />
  )
})

export const TabsContent = TabsPrimitive.Content

/* ---------------------------------------------------------------- Switch */

export const Switch = forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(function Switch({ className, ...props }, ref) {
  return (
    <SwitchPrimitive.Root
      ref={ref}
      className={cn(
        'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent',
        'transition-colors duration-200 ease-emphasis',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'data-[state=checked]:bg-brand-500 data-[state=unchecked]:bg-line-strong',
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        className={cn(
          'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-raised ring-0',
          'transition-transform duration-200 ease-emphasis',
          'data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0',
        )}
      />
    </SwitchPrimitive.Root>
  )
})

/* ------------------------------------------------------------- Separator */

export const Separator = forwardRef<
  React.ElementRef<typeof SeparatorPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(function Separator({ className, orientation = 'horizontal', decorative = true, ...props }, ref) {
  return (
    <SeparatorPrimitive.Root
      ref={ref}
      decorative={decorative}
      orientation={orientation}
      className={cn(
        'shrink-0 bg-line',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      {...props}
    />
  )
})

/* ---------------------------------------------------------------- Avatar */

export function Avatar({
  name,
  src,
  size = 'md',
  className,
}: {
  name?: string | null
  src?: string | null
  size?: 'xs' | 'sm' | 'md' | 'lg'
  className?: string
}) {
  const sizes = {
    xs: 'h-6 w-6 text-2xs',
    sm: 'h-7 w-7 text-2xs',
    md: 'h-9 w-9 text-xs',
    lg: 'h-12 w-12 text-sm',
  } as const

  return (
    <AvatarPrimitive.Root
      className={cn(
        'relative flex shrink-0 overflow-hidden rounded-full ring-1 ring-line-strong',
        sizes[size],
        className,
      )}
    >
      {src && <AvatarPrimitive.Image src={src} alt="" className="h-full w-full object-cover" />}
      <AvatarPrimitive.Fallback
        className={cn(
          'flex h-full w-full items-center justify-center font-semibold',
          'bg-gradient-to-br from-brand-600/30 to-accent/25 text-brand-100',
        )}
      >
        {initials(name)}
      </AvatarPrimitive.Fallback>
    </AvatarPrimitive.Root>
  )
}

/* -------------------------------------------------------------- Progress */

export function Progress({
  value,
  tone = 'brand',
  className,
  label,
}: {
  value: number
  tone?: 'brand' | 'ok' | 'warn' | 'danger'
  className?: string
  label?: string
}) {
  const clamped = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0
  const toneClass = {
    brand: 'bg-brand-500',
    ok: 'bg-ok',
    warn: 'bg-warn',
    danger: 'bg-danger',
  }[tone]

  return (
    <ProgressPrimitive.Root
      value={clamped}
      aria-label={label}
      className={cn('relative h-1.5 w-full overflow-hidden rounded-full bg-surface-overlay', className)}
    >
      <ProgressPrimitive.Indicator
        className={cn('h-full rounded-full transition-transform duration-500 ease-emphasis', toneClass)}
        style={{ transform: `translateX(-${100 - clamped}%)` }}
      />
    </ProgressPrimitive.Root>
  )
}

/* ------------------------------------------------------------------ Card */

export function Card({
  className,
  interactive,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        'panel',
        interactive &&
          'cursor-pointer transition-[border-color,background,transform,box-shadow] duration-200 ease-emphasis hover:-translate-y-0.5 hover:border-brand-500/30 hover:shadow-float',
        className,
      )}
      {...props}
    />
  )
}

/**
 * Card with perspective tilt + cursor-tracked glow ring.
 * Drop-in replacement for `<Card interactive>` where extra visual pop is wanted.
 */
export function GlowCard({
  className,
  accent = '#06b6d4',
  children,
  onClick,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { accent?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [tilt, setTilt] = useState({ x: 0, y: 0 })
  const [glow, setGlow] = useState({ x: 50, y: 50, show: false })

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top)  / r.height
    setTilt({ x: (py - 0.5) * -8, y: (px - 0.5) * 8 })
    setGlow({ x: px * 100, y: py * 100, show: true })
  }
  const reset = () => { setTilt({ x: 0, y: 0 }); setGlow(g => ({ ...g, show: false })) }

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={reset}
      onClick={onClick}
      style={{
        transform: `perspective(800px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
        transition: 'transform 0.12s ease-out',
        cursor: onClick ? 'pointer' : undefined,
      }}
      className={cn(
        'panel relative overflow-hidden',
        'hover:border-white/[0.12] hover:shadow-[0_8px_40px_rgba(0,0,0,0.3)]',
        className,
      )}
      {...props}
    >
      {/* Cursor glow spot */}
      <span
        className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 h-36 w-36 rounded-full transition-opacity duration-300"
        style={{
          left: `${glow.x}%`,
          top: `${glow.y}%`,
          background: `radial-gradient(circle, ${accent}1a, transparent 70%)`,
          opacity: glow.show ? 1 : 0,
        }}
        aria-hidden
      />
      {/* Top-edge accent line */}
      <span
        className="pointer-events-none absolute inset-x-0 top-0 h-px transition-opacity duration-300"
        style={{
          background: `linear-gradient(90deg, transparent, ${accent}50, transparent)`,
          opacity: glow.show ? 1 : 0,
        }}
        aria-hidden
      />
      <div className="relative">{children}</div>
    </div>
  )
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-start justify-between gap-4 p-5 pb-3', className)} {...props} />
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-sm font-semibold tracking-tight text-content', className)} {...props} />
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 pb-5', className)} {...props} />
}

/* ------------------------------------------------------------ SectionLabel */

/** Small uppercase section heading used throughout the shell. */
export function SectionLabel({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        'text-2xs font-semibold uppercase tracking-[0.18em] text-content-subtle',
        className,
      )}
      {...props}
    />
  )
}
