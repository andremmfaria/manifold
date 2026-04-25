import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { CardDetail } from '@/features/cards/CardDetail'
import { useCard, useCardTransactions, useCardBalances } from '@/features/cards/useCards'
import { TransactionTable } from '@/features/transactions/TransactionTable'
import { rootRoute } from '../__root'

export const cardDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cards/$cardId',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: CardDetailPage,
})

function CardDetailPage() {
  const { cardId } = useParams({ from: '/cards/$cardId' })
  const { data: card } = useCard(cardId)
  const { data: transactions = [] } = useCardTransactions(cardId)
  const { data: balances = [] } = useCardBalances(cardId)

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Card detail</h1>
        
        {card ? <CardDetail card={card} /> : <p>Loading card details...</p>}
        
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Balances</h2>
          {balances.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {balances.map((balance: any) => (
                <div key={balance.id} className="rounded-xl border bg-white p-4 shadow-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium text-slate-500">{balance.balance_type}</span>
                    <span className="text-xs rounded-full bg-slate-100 px-2 py-1 text-slate-600">
                      {new Date(balance.reference_date || balance.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="mt-2 text-2xl font-bold">
                    {balance.amount} {balance.currency}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500">No balances found.</p>
          )}
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Recent Transactions</h2>
          {transactions.length > 0 ? (
            <TransactionTable items={transactions} />
          ) : (
            <p className="text-slate-500">No recent transactions found.</p>
          )}
        </div>
      </div>
    </AppShell>
  )
}
