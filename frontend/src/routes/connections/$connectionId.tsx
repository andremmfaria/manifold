import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { ConnectionCard } from '@/features/connections/ConnectionCard'
import { useConnections } from '@/features/connections/useConnections'
import { rootRoute } from '../__root'

export const connectionDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/connections/$connectionId',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: ConnectionDetailPage,
})

function ConnectionDetailPage() {
  const { connectionId } = useParams({ from: '/connections/$connectionId' })
  const { data = [] } = useConnections()
  const connection = data.find((item) => item.id === connectionId)
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Connection detail</h1>
        {connection ? <ConnectionCard connection={connection} /> : <p>Connection not found.</p>}
      </div>
    </AppShell>
  )
}
