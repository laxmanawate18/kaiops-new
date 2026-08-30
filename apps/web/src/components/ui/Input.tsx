import { forwardRef, useId } from 'react'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ Field */

interface FieldProps {
  label?: string
  hint?: string
  error?: string
  required?: boolean
  htmlFor?: string
  children: React.ReactNode
  className?: string
}

/**
 * Label + control + hint/error, wired together.
 *
 * Every control in the app goes through this so `htmlFor`/`id` and
 * `aria-describedby` are never forgotten — the previous build had ~20
 * unlabelled inputs because each form wired this by hand.
 */
export function Field({ label, hint, error, required, htmlFor, children, className }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="flex items-center gap-1 text-xs font-medium tracking-wide text-content-muted"
        >
          {label}
          {required && (
            <span className="text-danger" aria-hidden>
              *
            </span>
          )}
          {required && <span className="sr-only">(required)</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="flex items-start gap-1.5 text-xs text-danger">
          <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p className="text-xs text-content-subtle">{hint}</p>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ Input */

const controlBase =
  'w-full rounded-md border bg-surface-sunken/60 px-3 text-sm text-content placeholder:text-content-subtle/70 ' +
  'transition-colors duration-150 ' +
  'focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-brand-500/50 ' +
  'disabled:cursor-not-allowed disabled:opacity-50'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
  leadingIcon?: React.ReactNode
  trailingSlot?: React.ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, leadingIcon, trailingSlot, ...props },
  ref,
) {
  return (
    <div className="relative flex items-center">
      {leadingIcon && (
        <span className="pointer-events-none absolute left-3 flex text-content-subtle" aria-hidden>
          {leadingIcon}
        </span>
      )}
      <input
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn(
          controlBase,
          'h-9.5',
          leadingIcon && 'pl-9',
          trailingSlot && 'pr-10',
          invalid ? 'border-danger/60 focus:ring-danger/40' : 'border-line-strong',
          className,
        )}
        {...props}
      />
      {trailingSlot && <span className="absolute right-2 flex items-center">{trailingSlot}</span>}
    </div>
  )
})

/* --------------------------------------------------------------- Textarea */

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        controlBase,
        'min-h-[80px] resize-y py-2.5 leading-relaxed',
        invalid ? 'border-danger/60 focus:ring-danger/40' : 'border-line-strong',
        className,
      )}
      {...props}
    />
  )
})

/* ------------------------------------------------- Convenience: TextField */

export interface TextFieldProps extends InputProps {
  label?: string
  hint?: string
  error?: string
}

/** Input pre-wrapped in a Field with a generated id. */
export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, required, id, ...props },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const describedBy = error || hint ? `${inputId}-desc` : undefined

  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId}>
      <Input
        ref={ref}
        id={inputId}
        required={required}
        invalid={Boolean(error)}
        aria-describedby={describedBy}
        {...props}
      />
    </Field>
  )
})
