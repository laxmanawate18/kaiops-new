import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

/**
 * Tracks the OS reduced-motion preference and reacts to live changes.
 *
 * Used to disable decorative animation (WebGL loops, infinite pulses) for
 * users who have asked the system for less movement.
 */
export function usePrefersReducedMotion(): boolean {
  const [prefersReduced, setPrefersReduced] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia(QUERY).matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia(QUERY)
    const onChange = (event: MediaQueryListEvent) => setPrefersReduced(event.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])

  return prefersReduced
}
