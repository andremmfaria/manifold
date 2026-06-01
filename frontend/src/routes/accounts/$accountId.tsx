import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AccountCard } from '@/features/accounts/AccountCard'
import { BalanceHistoryChart } from '@/features/accounts/BalanceHistoryChart'
import { useAccount, useBalanceHistory } from '@/features/accounts/useAccounts'
import { rootRoute } from '../__root'

export const accountDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accounts/$accountId',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: AccountDetailPage,
})

function AccountDetailPage() {
  const { accountId } = useParams({ from: '/accounts/$accountId' })
  const { data: account } = useAccount(accountId)
  const { data: balances = [] } = useBalanceHistory(accountId)
  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Account Detail</h1>
          <p className="mt-1 text-muted-foreground font-mono text-sm">{accountId}</p>
        </div>
        {account ? (
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            <AccountCard account={account} />
          </div>
        ) : null}
        <BalanceHistoryChart data={balances} />
      </div>
    </AppShell>
  )
}
