import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/lib/queryClient'
import { AuthProvider, useAuth } from '@/features/auth/AuthProvider'
import { rootRoute } from '@/routes/__root'
import { indexRoute } from '@/routes/index'
import { loginRoute } from '@/routes/login'
import { changePasswordRoute } from '@/routes/change-password'
import { connectionsRoute } from '@/routes/connections/index'
import { connectionDetailRoute } from '@/routes/connections/$connectionId'
import { accountsRoute } from '@/routes/accounts/index'
import { accountDetailRoute } from '@/routes/accounts/$accountId'
import { transactionsRoute } from '@/routes/transactions/index'
import { directDebitsRoute } from '@/routes/direct-debits/index'
import { standingOrdersRoute } from '@/routes/standing-orders/index'
import { cardsRoute } from '@/routes/cards/index'
import { settingsIndexRoute } from '@/routes/settings/index'
import { settingsUsersRoute } from '@/routes/settings/users'
import { settingsAccessRoute } from '@/routes/settings/access'
import { settingsSessionsRoute } from '@/routes/settings/sessions'
import { dashboardRoute } from '@/routes/dashboard/index'
import { alarmsIndexRoute } from '@/routes/alarms/index'
import { alarmsNewRoute } from '@/routes/alarms/new'
import { alarmDetailRoute } from '@/routes/alarms/$alarmId'
import { notifiersIndexRoute } from '@/routes/notifiers/index'
import { notifiersNewRoute } from '@/routes/notifiers/new'

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  changePasswordRoute,
  dashboardRoute,
  alarmsIndexRoute,
  alarmsNewRoute,
  alarmDetailRoute,
  notifiersIndexRoute,
  notifiersNewRoute,
  connectionsRoute,
  connectionDetailRoute,
  accountsRoute,
  accountDetailRoute,
  transactionsRoute,
  directDebitsRoute,
  standingOrdersRoute,
  cardsRoute,
  settingsIndexRoute,
  settingsUsersRoute,
  settingsAccessRoute,
  settingsSessionsRoute,
])

const router = createRouter({
  routeTree,
  context: {
    auth: undefined!,
  },
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

function AppRouter() {
  const auth = useAuth()
  return <RouterProvider router={router} context={{ auth }} />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRouter />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
