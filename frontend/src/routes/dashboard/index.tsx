import { createRoute, redirect } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { getDashboardSummary } from '@/api/dashboard'
import { rootRoute } from '../__root'

import { BalanceSummaryCard } from '@/features/dashboard/BalanceSummaryCard'
import { AlarmStatusWidget } from '@/features/dashboard/AlarmStatusWidget'
import { SyncStatusWidget } from '@/features/dashboard/SyncStatusWidget'
import { RecentTransactionsFeed } from '@/features/dashboard/RecentTransactionsFeed'
import { UpcomingDebitsWidget } from '@/features/dashboard/UpcomingDebitsWidget'

export const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: DashboardPage,
})

function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: getDashboardSummary,
  })

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center p-6 text-slate-500">
          Loading dashboard...
        </div>
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell>
        <div className="p-6 text-red-600">Failed to load dashboard</div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Dashboard</h1>
          <p className="mt-1 text-slate-500">Overview of your connected accounts and active alarms.</p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <BalanceSummaryCard accountsTotal={data.accounts_total} />
          <AlarmStatusWidget activeAlarmsCount={data.active_alarms_count} />
          <SyncStatusWidget lastSyncAt={data.last_sync_at} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3 items-start">
          <div className="lg:col-span-2">
            <RecentTransactionsFeed events={data.recent_events} />
          </div>
          <div>
            <UpcomingDebitsWidget debits={data.upcoming_debits} />
          </div>
        </div>
      </div>
    </AppShell>
  )
}
