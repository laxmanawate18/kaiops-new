import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <EmptyState
        icon={Compass}
        title="That page doesn't exist"
        description="The link may be stale, or the resource was removed."
        action={
          <Button variant="primary" size="sm" asChild>
            <Link to="/console">Back to console</Link>
          </Button>
        }
      />
    </div>
  )
}
