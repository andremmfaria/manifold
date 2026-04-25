import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAccounts } from '@/features/accounts/useAccounts'
import { StandingOrderList } from '@/features/standing-orders/StandingOrderList'
import { useStandingOrders } from '@/features/standing-orders/useStandingOrders'
import { rootRoute } from '../__root'

export const standingOrdersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/standing-orders',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: StandingOrdersPage,
})

function StandingOrdersPage() {
  const { data: accounts = [] } = useAccounts()
  const accountId = accounts[0]?.id || ''
  const { data = [] } = useStandingOrders(accountId)
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Standing orders</h1>
        <StandingOrderList items={data} />
      </div>
    </AppShell>
  )
}
