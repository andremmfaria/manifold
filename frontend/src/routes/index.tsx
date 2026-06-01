import { createRoute, redirect } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAuth } from '@/features/auth/useAuth'
import { getDashboardSummary } from '@/api/dashboard'
import { rootRoute } from './__root'
import { Skeleton } from '@/components/ui/skeleton'

import { BalanceSummaryCard } from '@/features/dashboard/BalanceSummaryCard'
import { AlarmStatusWidget } from '@/features/dashboard/AlarmStatusWidget'
import { SyncStatusWidget } from '@/features/dashboard/SyncStatusWidget'
import { RecentTransactionsFeed } from '@/features/dashboard/RecentTransactionsFeed'
import { UpcomingDebitsWidget } from '@/features/dashboard/UpcomingDebitsWidget'

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function DashboardSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: getDashboardSummary,
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
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
    )
  }

  if (error || !data) {
    return <div className="text-destructive">Failed to load dashboard</div>
  }

  return (
    <div className="space-y-6">
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
  )
}

function IndexPage() {
  const { username, firstName, lastName, role } = useAuth()
  const isSuperadmin = role === 'superadmin'
  const displayName =
    firstName && lastName
      ? `${capitalize(firstName)} ${capitalize(lastName)}`
      : username
        ? capitalize(username)
        : ''

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Hello {displayName}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {isSuperadmin
              ? 'Financial observability foundation ready.'
              : 'Overview of your connected accounts and active alarms.'}
          </p>
        </div>

        {/* Superadmin has no financial data — the API 403s; only members see the dashboard. */}
        {!isSuperadmin && <DashboardSection />}
      </div>
    </AppShell>
  )
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: IndexPage,
})
