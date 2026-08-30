import { forwardRef } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'outline' | 'danger' | 'subtle'
type Size = 'xs' | 'sm' | 'md' | 'lg' | 'icon' | 'icon-sm'

const VARIANTS: Record<Variant, string> = {
  // Gradient is a 6% lift, not a rainbow — it reads as a light source, not decoration.
  primary:
    'bg-gradient-to-b from-brand-400 to-brand-600 text-content-inverse font-semibold shadow-raised hover:from-brand-300 hover:to-brand-500 active:from-brand-500 active:to-brand-700 disabled:from-brand-800 disabled:to-brand-900',
  secondary:
    'bg-surface-overlay text-content border border-line-strong hover:bg-surface-overlay/70 hover:border-line-strong active:bg-surface-raised',
  outline:
    'border border-line-strong bg-transparent text-content hover:bg-surface-raised hover:border-brand-500/40',
  ghost: 'bg-transparent text-content-muted hover:bg-surface-raised hover:text-content',
  subtle: 'bg-surface-raised text-content-muted hover:bg-surface-overlay hover:text-content',
  danger:
    'bg-gradient-to-b from-danger to-danger/80 text-white font-semibold shadow-raised hover:brightness-110 active:brightness-95',
}

const SIZES: Record<Size, string> = {
  xs: 'h-7 px-2.5 text-2xs gap-1.5 rounded-sm',
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-md',
  md: 'h-9.5 px-4 text-sm gap-2 rounded-md',
  lg: 'h-11 px-5 text-sm gap-2 rounded-lg',
  icon: 'h-9.5 w-9.5 rounded-md',
  'icon-sm': 'h-8 w-8 rounded-md',
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  /** Render as the child element (e.g. a router `Link`) instead of a `button`. */
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', loading = false, asChild, children, disabled, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button'

  return (
    <Comp
      ref={ref}
      // Radix's Slot forwards props onto the child element. `disabled` is not
      // valid on an anchor, so it is only applied when we own the <button>.
      // A loading button must not be clickable — otherwise double-submit is trivial.
      {...(asChild ? {} : { disabled: disabled || loading, type: props.type ?? 'button' })}
      aria-busy={loading || undefined}
      aria-disabled={asChild && (disabled || loading) ? true : undefined}
      className={cn(
        'relative inline-flex select-none items-center justify-center whitespace-nowrap',
        'transition-[background,border-color,color,box-shadow,transform] duration-150 ease-emphasis',
        'active:translate-y-px',
        'disabled:pointer-events-none disabled:opacity-50',
        asChild && (disabled || loading) && 'pointer-events-none opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {/* Slot accepts exactly ONE child — React.Children.only throws otherwise.
          So when asChild is set we must not render a spinner sibling. */}
      {asChild ? (
        children
      ) : (
        <>
          {loading && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />}
          {children}
        </>
      )}
    </Comp>
  )
})
