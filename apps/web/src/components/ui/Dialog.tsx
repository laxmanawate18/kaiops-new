import { forwardRef } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X, AlertTriangle, Trash2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './Button'

/**
 * Dialogs built on Radix.
 *
 * Radix gives us focus trapping, focus restore on close, Escape handling,
 * `aria-modal`, scroll locking and inert backgrounding for free. The previous
 * build hand-rolled five modals and got none of those.
 */

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

const DialogOverlay = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(function DialogOverlay({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Overlay
      ref={ref}
      className={cn(
        'fixed inset-0 z-50 bg-canvas/75 backdrop-blur-sm',
        'data-[state=open]:animate-in data-[state=open]:fade-in-0',
        'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
        className,
      )}
      {...props}
    />
  )
})

export interface DialogContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  showClose?: boolean
}

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
} as const

export const DialogContent = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(function DialogContent({ className, children, size = 'md', showClose = true, ...props }, ref) {
  return (
    <DialogPrimitive.Portal>
      <DialogOverlay />
      <DialogPrimitive.Content
        ref={ref}
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2',
          'panel-raised max-h-[calc(100vh-4rem)] overflow-y-auto scrollbar-thin',
          'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
          'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          'duration-200',
          SIZES[size],
          className,
        )}
        {...props}
      >
        {children}
        {showClose && (
          <DialogPrimitive.Close
            className={cn(
              'absolute right-3.5 top-3.5 rounded-md p-1.5 text-content-subtle',
              'transition-colors hover:bg-surface-overlay hover:text-content',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
            )}
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
})

export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('space-y-1.5 border-b border-line px-6 py-5 pr-12', className)} {...props} />
}

export function DialogBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-6 py-5', className)} {...props} />
}

export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse gap-2 border-t border-line bg-surface-sunken/40 px-6 py-4 sm:flex-row sm:justify-end',
        className,
      )}
      {...props}
    />
  )
}

export const DialogTitle = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(function DialogTitle({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Title
      ref={ref}
      className={cn('text-base font-semibold tracking-tight text-content', className)}
      {...props}
    />
  )
})

export const DialogDescription = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(function DialogDescription({ className, ...props }, ref) {
  return (
    <DialogPrimitive.Description
      ref={ref}
      className={cn('text-sm leading-relaxed text-content-muted', className)}
      {...props}
    />
  )
})

/* ----------------------------------------------------------- ConfirmDialog */

type ConfirmTone = 'danger' | 'warning' | 'info'

const TONE_META: Record<
  ConfirmTone,
  { icon: React.ElementType; iconClass: string; ringClass: string; variant: 'danger' | 'primary' }
> = {
  danger: {
    icon: Trash2,
    iconClass: 'text-danger',
    ringClass: 'bg-danger/10 ring-danger/20',
    variant: 'danger',
  },
  warning: {
    icon: AlertTriangle,
    iconClass: 'text-warn',
    ringClass: 'bg-warn/10 ring-warn/20',
    variant: 'primary',
  },
  info: {
    icon: Info,
    iconClass: 'text-info',
    ringClass: 'bg-info/10 ring-info/20',
    variant: 'primary',
  },
}

export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void | Promise<void>
  title: string
  description?: React.ReactNode
  confirmText?: string
  cancelText?: string
  tone?: ConfirmTone
  loading?: boolean
}

/**
 * The single confirmation surface for the whole app.
 *
 * This replaces every `window.confirm` — those block the main thread, ignore
 * the design system, and can't show context about what's being destroyed.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  tone = 'danger',
  loading = false,
}: ConfirmDialogProps) {
  const meta = TONE_META[tone]
  const Icon = meta.icon

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="sm" showClose={false}>
        <DialogBody className="flex gap-4 pt-6">
          <div
            className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-1', meta.ringClass)}
          >
            <Icon className={cn('h-5 w-5', meta.iconClass)} aria-hidden />
          </div>
          <div className="space-y-1.5 pt-0.5">
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            variant={meta.variant}
            onClick={() => void onConfirm()}
            loading={loading}
            // Confirm is the primary action here, so it takes initial focus.
            autoFocus
          >
            {confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
