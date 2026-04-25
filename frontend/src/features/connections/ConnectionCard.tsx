import type { Connection } from '@/api/connections'
import { ConnectionStatusBadge } from './ConnectionStatusBadge'

export function ConnectionCard({ connection, onSync }: { connection: Connection; onSync?: () => void }) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">{connection.display_name || connection.provider_type}</h3>
          <p className="text-sm text-slate-500">{connection.provider_type}</p>
        </div>
        <ConnectionStatusBadge status={connection.status} />
      </div>
      <dl className="mt-4 grid gap-2 text-sm text-slate-600">
        <div className="flex justify-between gap-3"><dt>Auth</dt><dd>{connection.auth_status}</dd></div>
        <div className="flex justify-between gap-3"><dt>Consent</dt><dd>{connection.consent_expires_at || '—'}</dd></div>
        <div className="flex justify-between gap-3"><dt>Last sync</dt><dd>{connection.last_sync_at || 'Never'}</dd></div>
      </dl>
      {onSync ? (
        <button className="mt-4 rounded border px-3 py-2 text-sm" onClick={onSync} type="button">
          Run sync
        </button>
      ) : null}
    </div>
  )
}
