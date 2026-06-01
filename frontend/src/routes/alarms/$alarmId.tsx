import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmStateBadge } from '@/features/alarms/AlarmStateBadge'
import { AlarmHistory } from '@/features/alarms/AlarmHistory'
import { useAlarm, useMuteAlarm, useUnmuteAlarm } from '@/features/alarms/useAlarms'
import { BellOff, BellRing } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { rootRoute } from '../__root'

export const alarmDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/alarms/$alarmId',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: AlarmDetailPage,
})

function AlarmDetailPage() {
  const { alarmId } = useParams({ from: '/alarms/$alarmId' })
  const { data: alarm, isLoading } = useAlarm(alarmId)
  const { mutate: muteAlarm, isPending: isMuting } = useMuteAlarm()
  const { mutate: unmuteAlarm, isPending: isUnmuting } = useUnmuteAlarm()

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6 p-6 max-w-5xl mx-auto">
          <Skeleton className="h-24 rounded-xl" />
          <div className="grid md:grid-cols-2 gap-6">
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (!alarm) {
    return (
      <AppShell>
        <div className="p-12 text-center text-destructive">Alarm not found</div>
      </AppShell>
    )
  }

  const handleMute = () => {
    const nextWeek = new Date()
    nextWeek.setDate(nextWeek.getDate() + 7)
    muteAlarm({ id: alarm.id, mute_until: nextWeek.toISOString() })
  }

  const handleUnmute = () => {
    unmuteAlarm(alarm.id)
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-5xl mx-auto">
        <Card>
          <CardContent className="flex items-center justify-between py-6">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
                {alarm.name}
                <AlarmStateBadge state={alarm.state} />
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                ID: <span className="font-mono">{alarm.id}</span>
              </p>
            </div>
            <div>
              {alarm.state === 'muted' ? (
                <Button variant="outline" onClick={handleUnmute} disabled={isUnmuting}>
                  <BellRing className="h-4 w-4" />
                  {isUnmuting ? 'Unmuting...' : 'Unmute'}
                </Button>
              ) : (
                <Button variant="outline" onClick={handleMute} disabled={isMuting}>
                  <BellOff className="h-4 w-4" />
                  {isMuting ? 'Muting...' : 'Mute for 7 days'}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between border-b border-border pb-2">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="font-medium text-foreground">{alarm.status}</dd>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <dt className="text-muted-foreground">Accounts Monitored</dt>
                  <dd className="font-medium text-foreground">{alarm.account_ids.length}</dd>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <dt className="text-muted-foreground">Notifiers Linked</dt>
                  <dd className="font-medium text-foreground">{alarm.notifier_ids.length}</dd>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <dt className="text-muted-foreground">Repeat Count</dt>
                  <dd className="font-medium text-foreground">{alarm.repeat_count}</dd>
                </div>
                <div className="flex justify-between border-b border-border pb-2">
                  <dt className="text-muted-foreground">Cooldown</dt>
                  <dd className="font-medium text-foreground">{alarm.cooldown_minutes}m</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle>Rule Condition</CardTitle>
            </CardHeader>
            <CardContent className="flex-1">
              <div className="bg-foreground/5 border border-border p-4 rounded-lg overflow-auto text-xs font-mono text-foreground flex-1">
                <pre>{JSON.stringify(alarm.condition, null, 2)}</pre>
              </div>
            </CardContent>
          </Card>
        </div>

        <div>
          <h2 className="text-lg font-semibold tracking-tight text-foreground mb-4">
            Evaluation History
          </h2>
          <AlarmHistory alarmId={alarm.id} />
        </div>
      </div>
    </AppShell>
  )
}
