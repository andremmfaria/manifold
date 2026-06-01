import { useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { ConnectionCard } from '@/features/connections/ConnectionCard'
import { useConnections, useSyncConnection } from '@/features/connections/useConnections'
import { Button } from '@/components/ui/button'
import { rootRoute } from '../__root'

export const connectionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/connections',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: ConnectionsPage,
})

function ConnectionsPage() {
  const { data = [] } = useConnections()
  const sync = useSyncConnection()
  const syncAll = useSyncConnection()
  const navigate = useNavigate()
  const [isSyncingAll, setIsSyncingAll] = useState(false)

  async function handleSyncAll() {
    setIsSyncingAll(true)
    try {
      const results = await Promise.allSettled(data.map((c) => syncAll.mutateAsync(c.id)))
      const fulfilled = results.filter((r) => r.status === 'fulfilled').length
      const rejected = results.length - fulfilled
      if (rejected === 0) {
        toast.success(`Queued sync for ${fulfilled} connection${fulfilled !== 1 ? 's' : ''}`)
      } else {
        toast.warning(`Synced ${fulfilled}, ${rejected} failed`)
      }
    } finally {
      setIsSyncingAll(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Connections</h1>
            <p className="mt-1 text-muted-foreground">
              Provider health, consent state, manual sync.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              disabled={isSyncingAll || data.length === 0}
              onClick={handleSyncAll}
            >
              {isSyncingAll ? 'Syncing…' : 'Sync all'}
            </Button>
            <Button onClick={() => navigate({ to: '/connections/connect' })}>
              Connect new provider
            </Button>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {data.map((connection) => (
            <ConnectionCard
              key={connection.id}
              connection={connection}
              onSync={() => sync.mutate(connection.id)}
            />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
