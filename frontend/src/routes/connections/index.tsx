import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { ConnectionCard } from '@/features/connections/ConnectionCard'
import { useConnections, useSyncConnection } from '@/features/connections/useConnections'
import { Button } from '@/components/ui/button'
import { rootRoute } from '../__root'

export const connectionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/connections',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: ConnectionsPage,
})

function ConnectionsPage() {
  const { data = [] } = useConnections()
  const sync = useSyncConnection()
  const navigate = useNavigate()

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Connections</h1>
            <p className="mt-1 text-muted-foreground">Provider health, consent state, manual sync.</p>
          </div>
          <Button onClick={() => navigate({ to: '/connections/connect' })}>
            Connect new provider
          </Button>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((connection) => (
            <ConnectionCard key={connection.id} connection={connection} onSync={() => sync.mutate(connection.id)} />
          ))}
        </div>
      </div>
    </AppShell>
  )
}

