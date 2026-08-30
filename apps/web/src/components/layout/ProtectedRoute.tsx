import { Navigate, useLocation } from 'react-router-dom'
import { ShieldX } from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthProvider'
import { BootScreen } from './BootScreen'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'

interface ProtectedRouteProps {
  children: React.ReactNode
  /** Additional role gate on top of "must be signed in". */
  requires?: 'admin' | 'manage'
}

/**
 * Route guard.
 *
 * Two properties matter here:
 *  1. It renders nothing until `initializing` resolves, so protected content
 *     never flashes before the session check completes.
 *  2. The role it checks comes from `/auth/me`, not from client storage — so
 *     this is a UX guard on top of real server-side authorisation, not a
 *     substitute for it.
 */
export function ProtectedRoute({ children, requires }: ProtectedRouteProps) {
  const { isAuthenticated, initializing, isAdmin, canManage } = useAuth()
  const location = useLocation()

  if (initializing) return <BootScreen />

  if (!isAuthenticated) {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }

  const allowed = requires === 'admin' ? isAdmin : requires === 'manage' ? canManage : true

  if (!allowed) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          icon={ShieldX}
          title="You don't have access to this area"
          description={
            requires === 'admin'
              ? 'This section is restricted to administrators. If you believe you should have access, ask an admin to update your role.'
              : 'This section is restricted to team leads and administrators.'
          }
          action={
            <Button variant="outline" size="sm" asChild>
              <a href="/console">Back to console</a>
            </Button>
          }
        />
      </div>
    )
  }

  return <>{children}</>
}
