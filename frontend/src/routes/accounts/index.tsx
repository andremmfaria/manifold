import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AccountCard } from '@/features/accounts/AccountCard'
import { useAccounts } from '@/features/accounts/useAccounts'
import { rootRoute } from '../__root'

export const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accounts',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: AccountsPage,
})

function AccountsPage() {
  const { data = [] } = useAccounts()
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Accounts</h1>
          <p className="mt-1 text-slate-600">Canonical accounts with latest derived balance.</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {data.map((account) => (
            <AccountCard key={account.id} account={account} />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
