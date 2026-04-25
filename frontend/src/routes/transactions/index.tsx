import { useState } from 'react'
import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { TransactionFilters } from '@/features/transactions/TransactionFilters'
import { TransactionTable } from '@/features/transactions/TransactionTable'
import { useTransactions } from '@/features/transactions/useTransactions'
import { rootRoute } from '../__root'

export const transactionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/transactions',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: TransactionsPage,
})

function TransactionsPage() {
  const [accountId, setAccountId] = useState('')
  const { data = [] } = useTransactions(accountId ? { account_id: accountId } : undefined)
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Transactions</h1>
          <p className="mt-1 text-slate-600">Filterable canonical transaction feed.</p>
        </div>
        <TransactionFilters accountId={accountId} onChange={setAccountId} />
        <TransactionTable items={data} />
      </div>
    </AppShell>
  )
}
