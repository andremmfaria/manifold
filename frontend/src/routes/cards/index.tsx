import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { CardList } from '@/features/cards/CardList'
import { useCards } from '@/features/cards/useCards'
import { rootRoute } from '../__root'

export const cardsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cards',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: CardsPage,
})

function CardsPage() {
  const { data = [] } = useCards()
  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-semibold">Cards</h1>
        <CardList items={data} />
      </div>
    </AppShell>
  )
}
