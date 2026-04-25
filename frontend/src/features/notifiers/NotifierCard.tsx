import type { Notifier } from '@/types/notifier'
import { Bell, Activity, Send } from 'lucide-react'

export function NotifierCard({ 
  notifier, 
  onTest,
  isTesting = false 
}: { 
  notifier: Notifier; 
  onTest?: () => void;
  isTesting?: boolean;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border bg-white p-4 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
          <Bell className="h-5 w-5 text-slate-600" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-slate-900">{notifier.name}</h3>
            <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 uppercase tracking-wide">
              {notifier.type}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <span className={`inline-flex h-2 w-2 rounded-full ${notifier.is_enabled ? 'bg-green-500' : 'bg-slate-300'}`} />
            {notifier.is_enabled ? 'Active' : 'Disabled'}
          </div>
        </div>
      </div>
      <div>
        <button
          onClick={onTest}
          disabled={isTesting || !notifier.is_enabled}
          className="inline-flex items-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
        >
          {isTesting ? <Activity className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Test
        </button>
      </div>
    </div>
  )
}
