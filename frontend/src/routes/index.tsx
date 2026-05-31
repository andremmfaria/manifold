import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from './__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAuth } from '@/features/auth/useAuth'

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function IndexPage() {
  const { username, firstName, lastName } = useAuth()
  const displayName =
    firstName && lastName
      ? `${capitalize(firstName)} ${capitalize(lastName)}`
      : username
        ? capitalize(username)
        : ''

  return (
    <AppShell>
      <div className="p-6">
        <h1 className="text-2xl font-semibold">Hello {displayName}</h1>
        <p className="mt-2 text-slate-600">Financial observability foundation ready.</p>
      </div>
    </AppShell>
  )
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: IndexPage,
})
