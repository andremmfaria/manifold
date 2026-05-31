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
  const { data = [], isLoading } = useAccounts()
  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Accounts</h1>
          <p className="mt-1 text-muted-foreground">Canonical accounts with latest derived balance.</p>
        </div>
        {isLoading ? (
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {[1, 2, 3].map((n) => (
              <div key={n} className="rounded-xl bg-card ring-1 ring-foreground/10 p-4 space-y-3 animate-pulse">
                <div className="h-4 w-2/3 rounded bg-muted" />
                <div className="h-3 w-1/2 rounded bg-muted" />
                <div className="h-8 w-1/3 rounded bg-muted mt-4" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {data.map((account) => (
              <AccountCard key={account.id} account={account} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
