import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { DirectDebitList } from '@/features/direct-debits/DirectDebitList'
import { useAccounts } from '@/features/accounts/useAccounts'
import { useDirectDebits } from '@/features/direct-debits/useDirectDebits'
import { rootRoute } from '../__root'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export const directDebitsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/direct-debits',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: DirectDebitsPage,
})

function DirectDebitsPage() {
  const { data: accounts = [], isLoading: accountsLoading } = useAccounts()
  const accountId = accounts[0]?.id || ''
  const { data = [], isLoading: debitsLoading } = useDirectDebits(accountId)

  const isLoading = accountsLoading || (!!accountId && debitsLoading)

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Direct Debits</h1>
          <p className="mt-1 text-muted-foreground">
            Recurring payments drawn from your connected account.
          </p>
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
              No accounts yet. Connect an account to see direct debits.
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="p-4">
              <DirectDebitList items={data} />
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  )
}
