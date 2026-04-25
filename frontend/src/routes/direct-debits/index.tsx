import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { DirectDebitList } from '@/features/direct-debits/DirectDebitList'
import { useAccounts } from '@/features/accounts/useAccounts'
import { useDirectDebits } from '@/features/direct-debits/useDirectDebits'
import { rootRoute } from '../__root'

export const directDebitsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/direct-debits',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: DirectDebitsPage,
})

function DirectDebitsPage() {
  const { data: accounts = [] } = useAccounts()
  const accountId = accounts[0]?.id || ''
  const { data = [] } = useDirectDebits(accountId)
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Direct debits</h1>
        <DirectDebitList items={data} />
      </div>
    </AppShell>
  )
}
