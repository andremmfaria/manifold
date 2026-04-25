import { createRoute, redirect, Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmCard } from '@/features/alarms/AlarmCard'
import { useAlarms, useMuteAlarm, useUnmuteAlarm } from '@/features/alarms/useAlarms'
import { rootRoute } from '../__root'

export const alarmsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/alarms',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
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
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Alarms</h1>
            <p className="mt-1 text-slate-500">Manage your active alert conditions and thresholds.</p>
          </div>
          <Link
            to="/alarms/new"
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            New Alarm
          </Link>
        </div>

        {isLoading ? (
          <div className="flex justify-center p-12 text-slate-500">Loading alarms...</div>
        ) : (
          <div className="grid gap-4">
            {data?.items.map((alarm) => (
              <Link key={alarm.id} to="/alarms/$alarmId" params={{ alarmId: alarm.id }} className="block group">
                <div className="group-hover:border-blue-400 group-hover:shadow-md transition-all rounded-xl">
                  <AlarmCard 
                    alarm={alarm} 
                    onMute={() => handleMute(alarm.id)}
                    onUnmute={() => handleUnmute(alarm.id)}
                  />
                </div>
              </Link>
            ))}
            {data?.items.length === 0 && (
              <div className="text-center p-12 border rounded-xl border-dashed bg-slate-50">
                <p className="text-slate-500">No alarms configured yet.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
