import { createRoute, redirect, useParams } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmStateBadge } from '@/features/alarms/AlarmStateBadge'
import { AlarmHistory } from '@/features/alarms/AlarmHistory'
import { useAlarm, useMuteAlarm, useUnmuteAlarm } from '@/features/alarms/useAlarms'
import { BellOff, BellRing } from 'lucide-react'
import { rootRoute } from '../__root'

export const alarmDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/alarms/$alarmId',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: AlarmDetailPage,
})

function AlarmDetailPage() {
  const { alarmId } = useParams({ from: '/alarms/$alarmId' })
  const { data: alarm, isLoading } = useAlarm(alarmId)
  const { mutate: muteAlarm, isPending: isMuting } = useMuteAlarm()
  const { mutate: unmuteAlarm, isPending: isUnmuting } = useUnmuteAlarm()

  if (isLoading) {
    return <AppShell><div className="p-12 text-center text-slate-500">Loading alarm details...</div></AppShell>
  }

  if (!alarm) {
    return <AppShell><div className="p-12 text-center text-red-500">Alarm not found</div></AppShell>
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
        <div className="flex items-center justify-between bg-white p-6 rounded-xl border shadow-sm">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-3">
              {alarm.name}
              <AlarmStateBadge state={alarm.state} />
            </h1>
            <p className="mt-1 text-sm text-slate-500">ID: <span className="font-mono">{alarm.id}</span></p>
          </div>
          <div>
            {alarm.state === 'muted' ? (
              <button
                onClick={handleUnmute}
                disabled={isUnmuting}
                className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
              >
                <BellRing className="h-4 w-4" />
                {isUnmuting ? 'Unmuting...' : 'Unmute'}
              </button>
            ) : (
              <button
                onClick={handleMute}
                disabled={isMuting}
                className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
              >
                <BellOff className="h-4 w-4" />
                {isMuting ? 'Muting...' : 'Mute for 7 days'}
              </button>
            )}
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-xl border shadow-sm">
            <h3 className="font-semibold text-slate-900 mb-4">Configuration</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between border-b pb-2">
                <dt className="text-slate-500">Status</dt>
                <dd className="font-medium">{alarm.status}</dd>
              </div>
              <div className="flex justify-between border-b pb-2">
                <dt className="text-slate-500">Accounts Monitored</dt>
                <dd className="font-medium">{alarm.account_ids.length}</dd>
              </div>
              <div className="flex justify-between border-b pb-2">
                <dt className="text-slate-500">Notifiers Linked</dt>
                <dd className="font-medium">{alarm.notifier_ids.length}</dd>
              </div>
              <div className="flex justify-between border-b pb-2">
                <dt className="text-slate-500">Repeat Count</dt>
                <dd className="font-medium">{alarm.repeat_count}</dd>
              </div>
              <div className="flex justify-between border-b pb-2">
                <dt className="text-slate-500">Cooldown</dt>
                <dd className="font-medium">{alarm.cooldown_minutes}m</dd>
              </div>
            </dl>
          </div>

          <div className="bg-white p-6 rounded-xl border shadow-sm flex flex-col">
            <h3 className="font-semibold text-slate-900 mb-4">Rule Condition</h3>
            <div className="bg-slate-900 text-slate-50 p-4 rounded-md overflow-auto text-xs font-mono flex-1">
              <pre>{JSON.stringify(alarm.condition, null, 2)}</pre>
            </div>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-semibold tracking-tight text-slate-900 mb-4">Evaluation History</h2>
          <AlarmHistory alarmId={alarm.id} />
        </div>
      </div>
    </AppShell>
  )
}
