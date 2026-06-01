import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'

// Dashboard was merged into the Overview page (`/`). Keep the route as a permanent
// redirect so existing bookmarks/links don't 404.
export const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  beforeLoad: () => {
    throw redirect({ to: '/' })
  },
})
