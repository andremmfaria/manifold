import { Bell, AlertTriangle } from 'lucide-react'

export function AlarmStatusWidget({ activeAlarmsCount }: { activeAlarmsCount: number }) {
  return (
    <div className={`rounded-xl border p-6 shadow-sm ${activeAlarmsCount > 0 ? 'bg-red-50 border-red-100' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-3">
        {activeAlarmsCount > 0 ? (
          <AlertTriangle className="h-5 w-5 text-red-600" />
        ) : (
          <Bell className="h-5 w-5 text-slate-500" />
        )}
        <h3 className={`font-medium ${activeAlarmsCount > 0 ? 'text-red-900' : 'text-slate-500'}`}>Active Alarms</h3>
      </div>
      <div className="mt-4">
        <span className={`text-4xl font-bold tracking-tight ${activeAlarmsCount > 0 ? 'text-red-700' : 'text-slate-900'}`}>
          {activeAlarmsCount}
        </span>
        <p className={`mt-1 text-sm ${activeAlarmsCount > 0 ? 'text-red-600' : 'text-slate-500'}`}>
          {activeAlarmsCount === 1 ? 'Alarm requires attention' : 'Alarms require attention'}
        </p>
      </div>
    </div>
  )
}
