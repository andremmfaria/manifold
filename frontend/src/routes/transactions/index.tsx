import { useMemo, useState } from 'react'
import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { TransactionFilters } from '@/features/transactions/TransactionFilters'
import { TransactionTable } from '@/features/transactions/TransactionTable'
import { useTransactions } from '@/features/transactions/useTransactions'
import { inRange, lastNDays } from '@/components/DateRangeFilter'
import type { Transaction } from '@/types/transaction'
import { rootRoute } from '../__root'

export const transactionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/transactions',
  beforeLoad: ({
    context,
    location,
  }: {
    context: { auth: AuthContextValue }
    location: { href: string }
  }) => {
    if (!context.auth.isAuthenticated)
      throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: TransactionsPage,
})

function TransactionsPage() {
  const [accountId, setAccountId] = useState('')
  const [range, setRange] = useState(() => lastNDays(30))
  const [currency, setCurrency] = useState('__all__')
  const [status, setStatus] = useState('__all__')

  const { data = [] } = useTransactions(accountId ? { account_id: accountId } : undefined)
  const transactions = data as Transaction[]

  // Derive option lists from full dataset before date/currency/status filtering
  const currencyOptions = useMemo(
    () =>
      Array.from(new Set(transactions.map((tx) => tx.currency).filter(Boolean) as string[])).sort(),
    [transactions],
  )
  const statusOptions = useMemo(
    () =>
      Array.from(new Set(transactions.map((tx) => tx.status).filter(Boolean) as string[])).sort(),
    [transactions],
  )

  const filtered = useMemo(
    () =>
      transactions.filter(
        (tx) =>
          inRange(tx.transaction_date, range) &&
          (currency === '__all__' || tx.currency === currency) &&
          (status === '__all__' || tx.status === status),
      ),
    [transactions, range, currency, status],
  )

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Transactions</h1>
          <p className="mt-1 text-muted-foreground">Filterable canonical transaction feed.</p>
        </div>
        <TransactionFilters
          accountId={accountId}
          onChange={setAccountId}
          range={range}
          onRangeChange={setRange}
          currency={currency}
          onCurrencyChange={setCurrency}
          currencyOptions={currencyOptions}
          status={status}
          onStatusChange={setStatus}
          statusOptions={statusOptions}
        />
        <TransactionTable items={filtered} />
      </div>
    </AppShell>
  )
}
