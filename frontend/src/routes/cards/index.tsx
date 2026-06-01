import { createRoute, redirect } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { CardList } from '@/features/cards/CardList'
import { useCards } from '@/features/cards/useCards'
import { rootRoute } from '../__root'

export const cardsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/cards',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: CardsPage,
})

function CardsPage() {
  const { data = [] } = useCards()
  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Cards</h1>
        <CardList items={data} />
      </div>
    </AppShell>
  )
}
