import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'

export const settingsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
    throw redirect({
      to: context.auth.role === 'superadmin' ? '/settings/users' : '/settings/access',
    })
  },
  component: () => <AppShell />,
})
