import { RefreshCcw } from 'lucide-react'

export function SyncStatusWidget({ lastSyncAt }: { lastSyncAt: string | null }) {
  const syncDate = lastSyncAt ? new Date(lastSyncAt) : null;
  const isStale = syncDate ? (new Date().getTime() - syncDate.getTime()) > 1000 * 60 * 60 * 24 : true; // 24h

  return (
    <div className={`rounded-xl border p-6 shadow-sm ${isStale && lastSyncAt ? 'bg-amber-50 border-amber-100' : 'bg-white border-slate-200'}`}>
      <div className="flex items-center gap-3">
        <RefreshCcw className={`h-5 w-5 ${isStale && lastSyncAt ? 'text-amber-600' : 'text-slate-500'}`} />
        <h3 className={`font-medium ${isStale && lastSyncAt ? 'text-amber-900' : 'text-slate-500'}`}>Last Sync</h3>
      </div>
      <div className="mt-4">
        <span className={`text-xl font-semibold tracking-tight ${isStale && lastSyncAt ? 'text-amber-700' : 'text-slate-900'}`}>
          {syncDate ? syncDate.toLocaleString() : 'Never'}
        </span>
        {isStale && lastSyncAt && (
          <p className="mt-1 text-sm text-amber-600">Data may be stale</p>
        )}
      </div>
    </div>
  )
}
