import { useMemo } from 'react'

/** Platform check for rendering the correct modifier key in shortcut hints. */
export function useIsMac(): boolean {
  return useMemo(() => {
    if (typeof navigator === 'undefined') return false
    return /Mac|iPod|iPhone|iPad/.test(navigator.platform || navigator.userAgent)
  }, [])
}
