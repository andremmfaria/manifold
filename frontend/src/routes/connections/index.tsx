import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { ConnectionCard } from '@/features/connections/ConnectionCard'
import { useConnections, useSyncConnection } from '@/features/connections/useConnections'
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
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Connections</h1>
            <p className="mt-1 text-slate-600">Provider health, consent state, manual sync.</p>
          </div>
          <button
            onClick={() => navigate({ to: '/connections/connect' })}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Connect new provider
          </button>
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

