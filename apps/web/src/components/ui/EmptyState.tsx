import { motion } from 'framer-motion'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './Button'
import { staggerContainer, staggerItem } from '@/lib/motion'

export interface EmptyStateProps {
  icon?: React.ElementType
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
  className?: string
  size?: 'sm' | 'md'
}

/**
 * The one empty-state surface. Every list, table and panel uses it so an
 * empty result never looks like a broken screen.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  size = 'md',
}: EmptyStateProps) {
  return (
    <motion.div
      variants={staggerContainer(0.06)}
      initial="initial"
      animate="animate"
      className={cn(
        'flex flex-col items-center justify-center text-center',
        size === 'md' ? 'gap-4 px-6 py-16' : 'gap-3 px-4 py-10',
        className,
      )}
    >
      {Icon && (
        <motion.div
          variants={staggerItem}
          className={cn(
            'relative flex items-center justify-center rounded-2xl',
            'border border-line bg-surface-raised/60',
            size === 'md' ? 'h-14 w-14' : 'h-11 w-11',
          )}
        >
          <div className="absolute inset-0 rounded-2xl bg-brand-500/[0.06] blur-xl" aria-hidden />
          <Icon
            className={cn('relative text-content-subtle', size === 'md' ? 'h-6 w-6' : 'h-5 w-5')}
            aria-hidden
          />
        </motion.div>
      )}

      <motion.div variants={staggerItem} className="max-w-sm space-y-1.5">
        <p className={cn('font-semibold text-content', size === 'md' ? 'text-sm' : 'text-xs')}>{title}</p>
        {description && (
          <p className="text-pretty text-xs leading-relaxed text-content-subtle">{description}</p>
        )}
      </motion.div>

      {action && (
        <motion.div variants={staggerItem} className="pt-1">
          {action}
        </motion.div>
      )}
    </motion.div>
  )
}

/**
 * Error state with a retry affordance.
 *
 * Shows the real message — an operator debugging a broken integration needs
 * the actual failure, not "Something went wrong".
 */
export function ErrorState({
  title = 'Could not load this view',
  message,
  onRetry,
  retrying,
  className,
}: {
  title?: string
  message?: string
  onRetry?: () => void
  retrying?: boolean
  className?: string
}) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center gap-4 px-6 py-14 text-center', className)}
      role="alert"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-danger/10 ring-1 ring-danger/20">
        <AlertTriangle className="h-5 w-5 text-danger" aria-hidden />
      </div>
      <div className="max-w-md space-y-1.5">
        <p className="text-sm font-semibold text-content">{title}</p>
        {message && (
          <p className="text-pretty break-words font-mono text-2xs leading-relaxed text-content-subtle">
            {message}
          </p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} loading={retrying}>
          {!retrying && <RefreshCw className="h-3.5 w-3.5" aria-hidden />}
          Retry
        </Button>
      )}
    </div>
  )
}
