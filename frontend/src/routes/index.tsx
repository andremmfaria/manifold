import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from './__root'
import { AppShell } from '@/components/layout/AppShell'

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: () => (
    <AppShell>
      <div className="p-6">
        <h1 className="text-2xl font-semibold">Hello Manifold</h1>
        <p className="mt-2 text-slate-600">Financial observability foundation ready.</p>
      </div>
    </AppShell>
  ),
})
