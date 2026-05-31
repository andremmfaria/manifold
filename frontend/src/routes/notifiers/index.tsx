import { createRoute, redirect, Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { NotifierCard } from '@/features/notifiers/NotifierCard'
import { useNotifiers, useTestNotifier } from '@/features/notifiers/useNotifiers'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { rootRoute } from '../__root'

export const notifiersIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/notifiers',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: NotifiersPage,
})

function NotifiersPage() {
  const { data, isLoading } = useNotifiers()
  const { mutate: testNotifier, isPending: isTesting } = useTestNotifier()

  const handleTest = (id: string) => {
    testNotifier(id, {
      onSuccess: () => alert('Test notification delivered successfully!'),
      onError: (err: any) => alert(`Failed to deliver test: ${err.message}`)
    })
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-4xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Notifiers</h1>
            <p className="mt-1 text-muted-foreground">Configure how you receive alarm notifications.</p>
          </div>
          <Button asChild>
            <Link to="/notifiers/new">
              <Plus className="h-4 w-4" />
              Add Notifier
            </Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4">
            <Skeleton className="h-20 rounded-xl" />
            <Skeleton className="h-20 rounded-xl" />
          </div>
        ) : (
          <div className="grid gap-4">
            {data?.items.map((notifier) => (
              <NotifierCard
                key={notifier.id}
                notifier={notifier}
                onTest={() => handleTest(notifier.id)}
                isTesting={isTesting}
              />
            ))}
            {data?.items.length === 0 && (
              <div className="text-center p-12 border border-border rounded-xl border-dashed bg-muted/30">
                <p className="text-muted-foreground">No notifiers configured yet.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
