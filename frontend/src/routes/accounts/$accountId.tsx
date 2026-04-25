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
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: AccountDetailPage,
})

function AccountDetailPage() {
  const { accountId } = useParams({ from: '/accounts/$accountId' })
  const { data: account } = useAccount(accountId)
  const { data: balances = [] } = useBalanceHistory(accountId)
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Account detail</h1>
        {account ? <AccountCard account={account} /> : null}
        <BalanceHistoryChart data={balances} />
      </div>
    </AppShell>
  )
}
