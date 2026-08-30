import { Suspense, lazy, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { CommandPalette } from './CommandPalette'
import { CanvasBoundary } from '@/components/three/CanvasBoundary'
import { useUiStore } from '@/stores/ui'

const AmbientField = lazy(() => import('@/components/three/AmbientField'))

// Per-route color accent for the ambient wash
const ROUTE_ACCENTS: Record<string, [string, string]> = {
  '/console':   ['rgba(6,182,212,0.06)',  'rgba(139,92,246,0.04)'],
  '/services':  ['rgba(139,92,246,0.07)', 'rgba(6,182,212,0.03)'],
  '/overview':  ['rgba(34,197,94,0.05)',  'rgba(6,182,212,0.04)'],
  '/feedback':  ['rgba(234,179,8,0.05)',  'rgba(239,68,68,0.03)'],
  '/admin':     ['rgba(239,68,68,0.05)',  'rgba(139,92,246,0.04)'],
}

function routeAccent(path: string): [string, string] {
  for (const [key, val] of Object.entries(ROUTE_ACCENTS)) {
    if (path.startsWith(key)) return val
  }
  return ['rgba(6,182,212,0.05)', 'rgba(139,92,246,0.04)']
}

export function AppShell() {
  const { pathname } = useLocation()
  const [c1, c2] = routeAccent(pathname)

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#05070d] text-content">

      {/* ── Persistent ambient 3D canvas ── */}
      <CanvasBoundary>
        <Suspense fallback={null}>
          <AmbientField
            className="pointer-events-none fixed inset-0 z-0 opacity-60"
            density="low"
          />
        </Suspense>
      </CanvasBoundary>

      {/* ── Route-aware color wash ── */}
      <div
        className="pointer-events-none fixed inset-0 z-[1] transition-all duration-700"
        aria-hidden
        style={{
          background: [
            `radial-gradient(ellipse 65% 50% at 10% 0%, ${c1}, transparent 65%)`,
            `radial-gradient(ellipse 50% 40% at 90% 100%, ${c2}, transparent 60%)`,
          ].join(','),
        }}
      />

      {/* ── Subtle grid overlay ── */}
      <div
        className="pointer-events-none fixed inset-0 z-[1] opacity-[0.025]"
        aria-hidden
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px),' +
            'linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
        }}
      />

      <Sidebar />

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>

      {/* ── A4: first-visit ⌘K hint ── */}
      <CommandHint />

      <CommandPalette />
    </div>
  )
}

/** One-time bottom-right nudge so people discover the command palette. */
function CommandHint() {
  const [show, setShow] = useState(false)
  const setCommandOpen = useUiStore((s) => s.setCommandOpen)

  useEffect(() => {
    if (localStorage.getItem('kaiops.cmdk-hint')) return
    const t = setTimeout(() => setShow(true), 3500)
    return () => clearTimeout(t)
  }, [])

  const dismiss = (open?: boolean) => {
    localStorage.setItem('kaiops.cmdk-hint', '1')
    setShow(false)
    if (open) setCommandOpen(true)
  }

  // Auto-dismiss the moment the palette is opened by any means.
  useEffect(() => {
    const unsub = useUiStore.subscribe((s) => {
      if (s.commandOpen) dismiss()
    })
    return unsub
  }, [])

  if (!show) return null
  return (
    <motion.button
      type="button"
      onClick={() => dismiss(true)}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="fixed bottom-5 right-5 z-50 hidden items-center gap-2 rounded-full border border-line-strong bg-surface-overlay/90 px-3.5 py-2 text-xs text-content-muted shadow-lg backdrop-blur transition-colors hover:border-brand-500/40 hover:text-content sm:flex"
    >
      <kbd className="rounded border border-line-strong bg-surface-raised px-1.5 py-0.5 font-mono text-[10px]">Ctrl</kbd>
      <span className="text-[10px]">+</span>
      <kbd className="rounded border border-line-strong bg-surface-raised px-1.5 py-0.5 font-mono text-[10px]">K</kbd>
      quick search
    </motion.button>
  )
}
