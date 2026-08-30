/**
 * CountUp — animated number ticker (easeOutCubic).
 * Renders `to` immediately when reduced-motion is preferred or `active` is false.
 */
import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

interface CountUpProps {
  to: number
  active?: boolean
  duration?: number
  className?: string
}

export function CountUp({ to, active = true, duration = 1100, className }: CountUpProps) {
  const reduced = useReducedMotion()
  const [value, setValue] = useState(active && !reduced ? 0 : to)
  const raf = useRef<number>(0)

  useEffect(() => {
    if (!active || reduced) {
      setValue(to)
      return
    }
    const start = performance.now()
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setValue(Math.round(eased * to))
      if (p < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [to, active, duration, reduced])

  return <span className={className}>{value.toLocaleString()}</span>
}
