import type { Alarm } from '@/types/alarm'
import { AlarmStateBadge } from './AlarmStateBadge'
import { BellOff, BellRing } from 'lucide-react'

export function AlarmCard({ alarm, onMute, onUnmute }: { alarm: Alarm; onMute?: () => void; onUnmute?: () => void }) {
  return (
    <div className="flex items-center justify-between rounded-xl border bg-white p-4 shadow-sm">
      <div>
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-slate-900">{alarm.name}</h3>
          <AlarmStateBadge state={alarm.state} />
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Last evaluated: {alarm.last_evaluated_at ? new Date(alarm.last_evaluated_at).toLocaleString() : 'Never'}
        </p>
      </div>
      <div>
        {alarm.state === 'muted' ? (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onUnmute?.(); }}
            className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            <BellRing className="h-4 w-4" />
            Unmute
          </button>
        ) : (
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onMute?.(); }}
            className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            <BellOff className="h-4 w-4" />
            Mute
          </button>
        )}
      </div>
    </div>
  )
}
