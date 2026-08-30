import { useState } from 'react'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog'
import { Button } from '@/components/ui/Button'
import { Field, Textarea } from '@/components/ui/Input'
import {
  FEEDBACK_CATEGORIES,
  FEEDBACK_CATEGORY_LABELS,
  type FeedbackCategoryValue,
} from '@/lib/api/types'
import { cn } from '@/lib/utils'

export interface FeedbackDraft {
  tags: FeedbackCategoryValue[]
  comment: string
  suggested_response: string
}

/**
 * Collected on a thumbs-down. A bare downvote tells the team nothing
 * actionable; a category plus "what it should have said" becomes a training
 * example.
 */
export function FeedbackDialog({
  open,
  onOpenChange,
  onSubmit,
  submitting,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (draft: FeedbackDraft) => void
  submitting?: boolean
}) {
  const [tags, setTags] = useState<FeedbackCategoryValue[]>([])
  const [comment, setComment] = useState('')
  const [suggested, setSuggested] = useState('')

  const reset = () => {
    setTags([])
    setComment('')
    setSuggested('')
  }

  const toggle = (tag: FeedbackCategoryValue) => {
    setTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]))
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent size="md">
        <DialogHeader>
          <DialogTitle>What went wrong?</DialogTitle>
          <DialogDescription>
            This goes to your team leads for review and becomes training data for the agent.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-5">
          <Field label="Category" hint="Pick everything that applies.">
            <div className="flex flex-wrap gap-2">
              {FEEDBACK_CATEGORIES.map((tag) => {
                const selected = tags.includes(tag)
                return (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggle(tag)}
                    aria-pressed={selected}
                    className={cn(
                      'rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-150',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
                      selected
                        ? 'border-brand-500/40 bg-brand-500/15 text-brand-200'
                        : 'border-line-strong bg-surface-sunken text-content-muted hover:border-line-strong hover:text-content',
                    )}
                  >
                    {FEEDBACK_CATEGORY_LABELS[tag]}
                  </button>
                )
              })}
            </div>
          </Field>

          <Field label="What happened?" htmlFor="fb-comment">
            <Textarea
              id="fb-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="It missed the OOMKill on the payments pod…"
              rows={3}
              maxLength={1000}
            />
          </Field>

          <Field
            label="What should it have said?"
            htmlFor="fb-suggested"
            hint="Optional, but this is the most valuable part for training."
          >
            <Textarea
              id="fb-suggested"
              value={suggested}
              onChange={(e) => setSuggested(e.target.value)}
              placeholder="The root cause was a memory limit set below the JVM heap size…"
              rows={3}
              maxLength={2000}
            />
          </Field>
        </DialogBody>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={submitting}
            disabled={tags.length === 0}
            onClick={() => onSubmit({ tags, comment, suggested_response: suggested })}
          >
            Submit feedback
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
