import { memo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * Renders agent output as real Markdown.
 *
 * The previous UI rendered LLM responses as raw text inside a `<p>` with
 * `whitespace-pre-wrap`, so every `**bold**`, table and bullet list showed as
 * literal syntax — and agent output is markdown-heavy by nature. This is the
 * single largest readability change in the rewrite.
 *
 * Safety: `react-markdown` does not render raw HTML unless `rehype-raw` is
 * added. It is deliberately not added, so model output cannot inject markup.
 */

function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard blocked — the code is still selectable */
    }
  }

  return (
    <div className="group/code relative my-3 overflow-hidden rounded-lg border border-line-strong bg-surface-sunken">
      <div className="flex items-center justify-between border-b border-line bg-surface-raised/60 px-3 py-1.5">
        <span className="font-mono text-2xs uppercase tracking-wider text-content-subtle">
          {language || 'text'}
        </span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1.5 rounded px-1.5 py-1 font-mono text-2xs text-content-subtle transition-colors hover:bg-surface-overlay hover:text-content focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          aria-label={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 text-ok" aria-hidden />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" aria-hidden />
              Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto scrollbar-thin p-3.5">
        <code className="font-mono text-xs leading-relaxed text-content-muted">{code}</code>
      </pre>
    </div>
  )
}

export const Markdown = memo(function Markdown({
  children,
  className,
}: {
  children: string
  className?: string
}) {
  return (
    <div className={cn('text-sm leading-relaxed text-content-muted', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-4 text-base font-semibold tracking-tight text-content first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 mt-4 text-sm font-semibold tracking-tight text-content first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1.5 mt-3 text-sm font-semibold text-content first:mt-0">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mb-1.5 mt-3 text-xs font-semibold uppercase tracking-wide text-content-muted first:mt-0">
              {children}
            </h4>
          ),
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-content">{children}</strong>,
          em: ({ children }) => <em className="italic text-content-muted">{children}</em>,

          ul: ({ children }) => <ul className="mb-3 ml-1 space-y-1.5 last:mb-0">{children}</ul>,
          ol: ({ children }) => (
            <ol className="mb-3 ml-1 list-decimal space-y-1.5 pl-4 last:mb-0 marker:text-content-subtle">
              {children}
            </ol>
          ),
          li: ({ children, ...props }) => {
            // Unordered items get a custom marker; ordered ones keep the number.
            const ordered = 'ordered' in props && props.ordered
            if (ordered) return <li className="pl-1">{children}</li>
            return (
              <li className="relative flex gap-2.5">
                <span className="mt-[0.55em] h-1 w-1 shrink-0 rounded-full bg-brand-400/70" aria-hidden />
                <span className="min-w-0 flex-1">{children}</span>
              </li>
            )
          },

          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 font-medium text-brand-300 underline decoration-brand-500/40 underline-offset-2 transition-colors hover:text-brand-200 hover:decoration-brand-400"
            >
              {children}
              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
            </a>
          ),

          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 border-brand-500/40 bg-brand-500/[0.04] py-1 pl-3.5 pr-2 text-content-muted">
              {children}
            </blockquote>
          ),

          hr: () => <hr className="rule-fade my-4" />,

          code: ({ className: codeClass, children, ...props }) => {
            const match = /language-(\w+)/.exec(codeClass || '')
            const raw = String(children).replace(/\n$/, '')
            const isBlock = Boolean(match) || raw.includes('\n')

            if (!isBlock) {
              return (
                <code
                  className="rounded border border-line-strong bg-surface-sunken px-1.5 py-0.5 font-mono text-[0.85em] text-brand-200"
                  {...props}
                >
                  {children}
                </code>
              )
            }
            return <CodeBlock code={raw} language={match?.[1]} />
          },
          pre: ({ children }) => <>{children}</>,

          table: ({ children }) => (
            <div className="my-3 overflow-x-auto scrollbar-thin rounded-lg border border-line-strong">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-surface-raised/70">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-line px-3 py-2 text-left text-2xs font-semibold uppercase tracking-wider text-content-muted">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-line/60 px-3 py-2 align-top text-content-muted last:border-0">
              {children}
            </td>
          ),
          tr: ({ children }) => <tr className="transition-colors hover:bg-surface-raised/40">{children}</tr>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
})
