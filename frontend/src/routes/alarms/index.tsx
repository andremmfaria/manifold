import { createRoute, redirect, Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmCard } from '@/features/alarms/AlarmCard'
import { useAlarms, useMuteAlarm, useUnmuteAlarm } from '@/features/alarms/useAlarms'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { rootRoute } from '../__root'

export const alarmsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/alarms',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: AlarmsPage,
})

function AlarmsPage() {
  const { data, isLoading } = useAlarms()
  const { mutate: muteAlarm } = useMuteAlarm()
  const { mutate: unmuteAlarm } = useUnmuteAlarm()

  const handleMute = (id: string) => {
    const nextWeek = new Date()
    nextWeek.setDate(nextWeek.getDate() + 7)
    muteAlarm({ id, mute_until: nextWeek.toISOString() })
  }

  const handleUnmute = (id: string) => {
    unmuteAlarm(id)
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-5xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Alarms</h1>
            <p className="mt-1 text-muted-foreground">
              Manage your active alert conditions and thresholds.
            </p>
          </div>
          <Button asChild>
            <Link to="/alarms/new">
              <Plus className="h-4 w-4" />
              New Alarm
            </Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4">
            <Skeleton className="h-20 rounded-xl" />
            <Skeleton className="h-20 rounded-xl" />
            <Skeleton className="h-20 rounded-xl" />
          </div>
        ) : (
          <div className="grid gap-4">
            {data?.items.map((alarm) => (
              <Link
                key={alarm.id}
                to="/alarms/$alarmId"
                params={{ alarmId: alarm.id }}
                className="block group"
              >
                <div className="transition-all group-hover:ring-2 group-hover:ring-primary/40 rounded-xl">
                  <AlarmCard
                    alarm={alarm}
                    onMute={() => handleMute(alarm.id)}
                    onUnmute={() => handleUnmute(alarm.id)}
                  />
                </div>
              </Link>
            ))}
            {data?.items.length === 0 && (
              <div className="text-center p-12 border border-border rounded-xl border-dashed bg-muted/30">
                <p className="text-muted-foreground">No alarms configured yet.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
