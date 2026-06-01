import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { CardDetail } from '@/features/cards/CardDetail'
import { useCard, useCardTransactions, useCardBalances } from '@/features/cards/useCards'
import { TransactionTable } from '@/features/transactions/TransactionTable'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { rootRoute } from '../__root'

export const cardDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cards/$cardId',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
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
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Card detail</h1>

        {card ? (
          <CardDetail card={card} />
        ) : (
          <p className="text-muted-foreground">Loading card details...</p>
        )}

        <div className="space-y-4">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">Balances</h2>
          {balances.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {balances.map((balance: any) => (
                <Card key={balance.id}>
                  <CardContent className="pt-4">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium text-muted-foreground">
                        {balance.balance_type}
                      </span>
                      <Badge variant="secondary">
                        {new Date(
                          balance.reference_date || balance.created_at,
                        ).toLocaleDateString()}
                      </Badge>
                    </div>
                    <p className="mt-3 text-2xl font-bold text-foreground">
                      {balance.amount} {balance.currency}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No balances found.</p>
          )}
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">
            Recent Transactions
          </h2>
          {transactions.length > 0 ? (
            <TransactionTable items={transactions} />
          ) : (
            <p className="text-muted-foreground">No recent transactions found.</p>
          )}
        </div>
      </div>
    </AppShell>
  )
}
