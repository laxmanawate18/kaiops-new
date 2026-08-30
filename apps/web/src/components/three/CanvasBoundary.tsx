import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Rendered instead of the canvas when WebGL is unavailable or throws. */
  fallback?: ReactNode
}

interface State {
  failed: boolean
}

/**
 * Isolates WebGL failures.
 *
 * `<Canvas>` throws synchronously when a GL context can't be created — and
 * without a boundary that error propagates to the root and blanks the entire
 * application. That is not hypothetical: it happens on machines where the GPU
 * is blocklisted by policy, in some VDI/VM setups, in headless browsers, and
 * whenever a driver update puts Chrome into software-rendering-disabled mode.
 *
 * The 3D layer here is decorative (ambient field) or has a 2D equivalent
 * (topology → grid/list view), so degrading to nothing is always acceptable.
 * Blanking the login page never is.
 */
export class CanvasBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log once for diagnostics, but never surface a GL error to the user —
    // there is nothing they can do about it.
    console.warn('[kaiops] WebGL layer disabled:', error.message, info.componentStack)
  }

  render() {
    if (this.state.failed) return this.props.fallback ?? null
    return this.props.children
  }
}

/** Cheap probe so we can skip mounting a Canvas we know will fail. */
export function isWebGLAvailable(): boolean {
  if (typeof document === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext('webgl2') || canvas.getContext('webgl')),
    )
  } catch {
    return false
  }
}
