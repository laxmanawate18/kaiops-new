import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Loader2, Square } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useIsMac } from '@/hooks/useIsMac'

interface ComposerProps {
  onSend: (text: string) => void
  disabled?: boolean
  busy?: boolean
  placeholder?: string
}

const MAX_HEIGHT = 200

export function Composer({ onSend, disabled, busy, placeholder }: ComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isMac = useIsMac()

  // Grow with content up to a cap, then scroll internally.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [value])

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled || busy) return
    onSend(trimmed)
    setValue('')
    // Return focus so the next question can be typed immediately.
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter is a newline. This is the convention every
    // chat tool uses and the one people's fingers already know.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  const canSend = value.trim().length > 0 && !disabled && !busy

  return (
    <div className="px-4 pb-4 pt-2">
      <div
        className={cn(
          'relative rounded-2xl border bg-surface/80 shadow-float backdrop-blur-xl transition-colors duration-200',
          'focus-within:border-brand-500/40 focus-within:shadow-glow',
          disabled ? 'border-line opacity-60' : 'border-line-strong',
        )}
      >
        <label htmlFor="composer" className="sr-only">
          Describe the incident or ask a question
        </label>
        <textarea
          id="composer"
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          rows={1}
          placeholder={
            placeholder ?? 'Describe what is failing, or ask about a service…'
          }
          className={cn(
            'block w-full resize-none bg-transparent px-4 py-3.5 pr-14 text-sm leading-relaxed text-content',
            'placeholder:text-content-subtle/80 focus:outline-none disabled:cursor-not-allowed',
            'scrollbar-thin',
          )}
          style={{ maxHeight: MAX_HEIGHT }}
        />

        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label={busy ? 'Agent is working' : 'Send message'}
          className={cn(
            'absolute bottom-2.5 right-2.5 flex h-9 w-9 items-center justify-center rounded-xl',
            'transition-all duration-200 ease-emphasis',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
            canSend
              ? 'bg-gradient-to-b from-brand-400 to-brand-600 text-content-inverse shadow-raised hover:from-brand-300 hover:to-brand-500 active:scale-95'
              : 'bg-surface-overlay text-content-subtle',
          )}
        >
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : disabled ? (
            <Square className="h-3.5 w-3.5" aria-hidden />
          ) : (
            <ArrowUp className="h-4 w-4" strokeWidth={2.5} aria-hidden />
          )}
        </button>
      </div>

      <p className="mt-2 px-1 text-center text-[10px] text-content-subtle/70">
        <kbd className="font-mono">Enter</kbd> to send ·{' '}
        <kbd className="font-mono">{isMac ? '⇧' : 'Shift'}+Enter</kbd> for a new line · KaiOPS can be
        wrong — verify before you act on it
      </p>
    </div>
  )
}
