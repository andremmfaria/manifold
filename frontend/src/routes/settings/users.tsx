import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'

export const settingsUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/users',
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
    if (context.auth.role !== 'superadmin') throw redirect({ to: '/settings/access' })
  },
  component: () => (
    <AppShell>
      <div className="p-6">
        <h2 className="text-xl font-semibold">Users</h2>
        <p className="mt-2 text-slate-600">Superadmin user management lives here.</p>
      </div>
    </AppShell>
  ),
})
