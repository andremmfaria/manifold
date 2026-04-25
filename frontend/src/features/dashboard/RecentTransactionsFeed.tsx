import { Clock, ExternalLink } from 'lucide-react'
import type { DashboardSummary } from '@/types/dashboard'

export function RecentTransactionsFeed({ events }: { events: DashboardSummary['recent_events'] }) {
  if (!events?.length) {
    return (
      <div className="rounded-xl border bg-white p-6 shadow-sm flex flex-col items-center justify-center text-center">
        <Clock className="h-10 w-10 text-slate-300 mb-3" />
        <p className="text-slate-500">No recent activity detected.</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
        <h3 className="font-semibold text-slate-800">Recent Activity</h3>
      </div>
      <div className="divide-y divide-slate-100">
        {events.map((event, i) => (
          <div key={i} className="p-4 hover:bg-slate-50 transition-colors flex items-start gap-4">
            <div className="mt-1 h-2 w-2 rounded-full bg-blue-500 shrink-0"></div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900">
                {event.event_type.replace(/_/g, ' ').toUpperCase()}
              </p>
              <p className="text-xs text-slate-500 mt-0.5 truncate">
                Source: {event.source_type} | Account ID: <span className="font-mono">{event.account_id.substring(0, 8)}...</span>
              </p>
            </div>
            <div className="text-xs text-slate-400 whitespace-nowrap">
              {new Date(event.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
