import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAccounts } from '@/features/accounts/useAccounts'
import { StandingOrderList } from '@/features/standing-orders/StandingOrderList'
import { useStandingOrders } from '@/features/standing-orders/useStandingOrders'
import { rootRoute } from '../__root'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export const standingOrdersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/standing-orders',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: StandingOrdersPage,
})

function StandingOrdersPage() {
  const { data: accounts = [], isLoading: accountsLoading } = useAccounts()
  const accountId = accounts[0]?.id || ''
  const { data = [], isLoading: ordersLoading } = useStandingOrders(accountId)

  const isLoading = accountsLoading || (!!accountId && ordersLoading)

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Standing Orders</h1>
          <p className="mt-1 text-muted-foreground">Scheduled recurring transfers from your connected account.</p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ) : !accountId ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground text-sm">
              No accounts yet. Connect an account to see standing orders.
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader className="border-b">
              <CardTitle>All Standing Orders</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <StandingOrderList items={data} />
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  )
}
