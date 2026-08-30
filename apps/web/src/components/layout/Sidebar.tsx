import { useRef } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, useMotionValue, useSpring, AnimatePresence } from 'framer-motion'
import { Boxes, ChevronLeft, LayoutDashboard, MessageSquareCode, MessagesSquare, Users2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth/AuthProvider'
import { Tooltip } from '@/components/ui/primitives'
import { useUiStore } from '@/stores/ui'

interface NavItem {
  to: string; label: string; icon: React.ElementType
  requires?: 'admin' | 'manage'; hint?: string
  accent: string
}

const NAV: NavItem[] = [
  { to: '/console',  label: 'Console',  icon: MessageSquareCode, hint: 'Investigate an incident', accent: '#06b6d4' },
  { to: '/dashboard',label: 'Overview', icon: LayoutDashboard,   hint: 'Fleet health at a glance', accent: '#22c55e' },
  { to: '/services', label: 'Services', icon: Boxes,             hint: 'The registry',             accent: '#8b5cf6' },
  { to: '/feedback', label: 'Review',   icon: MessagesSquare,    hint: 'Triage agent answers',     accent: '#f59e0b', requires: 'manage' },
  { to: '/admin',    label: 'Access',   icon: Users2,            hint: 'Users and teams',          accent: '#ef4444', requires: 'admin'  },
]

// ── Magnetic nav item ─────────────────────────────────────────────────────────
function MagItem({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  const glowRef = useRef<HTMLSpanElement>(null)
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const sx = useSpring(mx, { stiffness: 280, damping: 22 })
  const sy = useSpring(my, { stiffness: 280, damping: 22 })

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect()
    const dx = (e.clientX - r.left - r.width  / 2) * 0.22
    const dy = (e.clientY - r.top  - r.height / 2) * 0.22
    mx.set(dx); my.set(dy)

    // Move glow with cursor
    if (glowRef.current) {
      glowRef.current.style.left = `${e.clientX - r.left}px`
      glowRef.current.style.top  = `${e.clientY - r.top}px`
    }
  }
  const reset = () => { mx.set(0); my.set(0) }

  const Icon = item.icon

  return (
    <div ref={ref} onMouseMove={onMove} onMouseLeave={reset} className="relative overflow-hidden rounded-lg">
      {/* Cursor glow */}
      <span
        ref={glowRef}
        className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 h-16 w-16 rounded-full opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{ background: `radial-gradient(circle, ${item.accent}18, transparent 70%)` }}
        aria-hidden
      />

      <NavLink to={item.to}>
        {({ isActive }) => (
          <motion.div
            style={{ x: sx, y: sy }}
            className={cn(
              'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium select-none',
              'transition-colors duration-150',
              collapsed && 'justify-center px-0',
              isActive ? 'text-white' : 'text-white/40 hover:text-white/80',
            )}
          >
            {/* Active background pill with glow */}
            <AnimatePresence>
              {isActive && (
                <motion.span
                  layoutId="nav-pill"
                  className="absolute inset-0 rounded-lg"
                  style={{
                    background: `linear-gradient(135deg, ${item.accent}22, ${item.accent}0a)`,
                    boxShadow: `0 0 0 1px ${item.accent}30, inset 0 0 20px ${item.accent}08`,
                  }}
                  transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  aria-hidden
                />
              )}
            </AnimatePresence>

            {/* Left accent bar */}
            <AnimatePresence>
              {isActive && (
                <motion.span
                  layoutId="nav-bar"
                  className="absolute -left-3 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full"
                  style={{ background: item.accent, boxShadow: `0 0 8px ${item.accent}` }}
                  initial={{ scaleY: 0, opacity: 0 }}
                  animate={{ scaleY: 1, opacity: 1 }}
                  exit={{ scaleY: 0, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  aria-hidden
                />
              )}
            </AnimatePresence>

            <Icon
              className={cn(
                'relative h-[18px] w-[18px] shrink-0 transition-all duration-200',
                isActive ? 'drop-shadow-[0_0_6px_var(--icon-glow)]' : 'text-white/35 group-hover:text-white/65',
              )}
              style={{ '--icon-glow': item.accent } as React.CSSProperties}
              aria-hidden
            />

            {!collapsed && (
              <span className="relative truncate text-[13px]">{item.label}</span>
            )}
          </motion.div>
        )}
      </NavLink>
    </div>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
export function Sidebar() {
  const { isAdmin, canManage } = useAuth()
  const collapsed = useUiStore((s) => s.sidebarCollapsed)
  const toggle    = useUiStore((s) => s.toggleSidebar)

  const visible = NAV.filter(item => {
    if (item.requires === 'admin')  return isAdmin
    if (item.requires === 'manage') return canManage
    return true
  })

  return (
    <aside
      className={cn(
        'relative z-30 flex shrink-0 flex-col',
        'border-r border-white/[0.06] bg-white/[0.03] backdrop-blur-xl',
        'transition-[width] duration-300 ease-out',
        collapsed ? 'w-[68px]' : 'w-[220px]',
      )}
    >
      {/* Sidebar inner glow */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{ background: 'linear-gradient(180deg, rgba(6,182,212,0.04) 0%, transparent 40%)' }}
        aria-hidden
      />

      {/* Brand */}
      <div className={cn(
        'relative z-10 flex h-16 items-center border-b border-white/[0.06]',
        collapsed ? 'justify-center px-3' : 'px-4',
      )}>
        <NavLink to="/console" className="flex items-center gap-2.5" aria-label="KaiOPS home">
          {/* Logo glow pulse */}
          <div className="relative flex h-8 w-8 shrink-0 items-center justify-center">
            <motion.div
              className="absolute inset-0 rounded-lg"
              animate={{ opacity: [0.3, 0.7, 0.3] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              style={{ background: 'radial-gradient(circle, rgba(6,182,212,0.4), transparent 70%)' }}
              aria-hidden
            />
            <svg viewBox="0 0 32 32" className="relative h-7 w-7">
              <rect width="32" height="32" rx="7" fill="rgba(6,182,212,0.12)" />
              <path d="M16 5.5 25 10.5v11L16 26.5 7 21.5v-11L16 5.5Zm0 3.2-6.2 3.45v6.7L16 22.3l6.2-3.45v-6.7L16 8.7Z"
                fill="rgb(6 182 212)" />
              <path d="M16 12.4 20 14.6 16 16.8 12 14.6 16 12.4Z" fill="rgb(165 243 252)" />
            </svg>
          </div>

          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              className="min-w-0 leading-tight"
            >
              <p className="text-[13px] font-bold tracking-[0.16em] text-white">KaiOPS</p>
              <p className="truncate text-[9px] font-medium uppercase tracking-[0.22em] text-cyan-400/60">
                Incidents End Here
              </p>
            </motion.div>
          )}
        </NavLink>
      </div>

      {/* Nav items */}
      <nav className="relative z-10 flex-1 space-y-0.5 overflow-y-auto p-2.5" aria-label="Primary">
        {visible.map(item => {
          const node = (
            <MagItem key={item.to} item={item} collapsed={collapsed} />
          )
          return collapsed ? (
            <Tooltip key={item.to} content={item.label} side="right">{node}</Tooltip>
          ) : node
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="relative z-10 border-t border-white/[0.06] p-2.5">
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium',
            'text-white/25 transition-colors hover:bg-white/[0.05] hover:text-white/60',
            collapsed && 'justify-center px-0',
          )}
        >
          <ChevronLeft
            className={cn('h-4 w-4 transition-transform duration-300', collapsed && 'rotate-180')}
            aria-hidden
          />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
