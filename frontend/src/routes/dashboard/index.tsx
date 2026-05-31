import { createRoute, redirect } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { getDashboardSummary } from '@/api/dashboard'
import { rootRoute } from '../__root'
import { Skeleton } from '@/components/ui/skeleton'

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
    // Superadmin has no financial data — the API 403s; send them to the overview instead.
    if (context.auth.role === 'superadmin') throw redirect({ to: '/' })
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
        <div className="space-y-6 p-6 max-w-7xl mx-auto">
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="mt-2 h-4 w-72" />
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <Skeleton className="h-36 rounded-xl" />
            <Skeleton className="h-36 rounded-xl" />
            <Skeleton className="h-36 rounded-xl" />
          </div>
          <div className="grid gap-6 lg:grid-cols-3 items-start">
            <Skeleton className="lg:col-span-2 h-64 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (error || !data) {
    return (
      <AppShell>
        <div className="p-6 text-destructive">Failed to load dashboard</div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
          <p className="mt-1 text-muted-foreground">Overview of your connected accounts and active alarms.</p>
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
