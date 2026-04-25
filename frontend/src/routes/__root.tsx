import { Outlet, createRootRouteWithContext } from '@tanstack/react-router'
import type { AuthContextValue } from '@/features/auth/AuthProvider'

export const rootRoute = createRootRouteWithContext<{ auth: AuthContextValue }>()({
  component: () => <Outlet />,
})
