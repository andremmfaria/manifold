import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'

export const settingsAccessRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/access',
  beforeLoad: ({ context }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: () => (
    <AppShell>
      <div className="p-6">
        <h2 className="text-xl font-semibold">Access delegation</h2>
        <p className="mt-2 text-slate-600">Manage grants you give to other users.</p>
      </div>
    </AppShell>
  ),
})
