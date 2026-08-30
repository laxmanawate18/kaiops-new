import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('skeleton', className)} aria-hidden {...props} />
}

/**
 * Skeletons should mirror the shape of what's loading, not be a generic
 * spinner — it keeps layout stable and makes the wait feel shorter.
 */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-3"
          style={{ width: i === lines - 1 ? '60%' : `${88 - i * 6}%` }}
        />
      ))}
    </div>
  )
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('panel space-y-4 p-5', className)}>
      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-9 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-1/3" />
          <Skeleton className="h-2.5 w-1/4" />
        </div>
      </div>
      <SkeletonText lines={2} />
    </div>
  )
}

export function SkeletonRow({ columns = 4 }: { columns?: number }) {
  return (
    <div className="flex items-center gap-4 px-4 py-3.5">
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={i} className={cn('h-3', i === 0 ? 'w-1/4' : 'flex-1')} />
      ))}
    </div>
  )
}
