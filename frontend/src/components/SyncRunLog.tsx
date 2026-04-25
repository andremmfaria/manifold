import { useQuery } from '@tanstack/react-query'
import { client } from '@/api/client'
import { StatusBadge } from './StatusBadge'
import { Skeleton } from '@/components/ui/skeleton'

interface SyncRunLogProps {
  connectionId: string
}

interface SyncRun {
  id: string
  status: string
  started_at: string
  completed_at: string | null
  accounts_synced: number
  error_code: string | null
}

export function SyncRunLog({ connectionId }: SyncRunLogProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['connections', connectionId, 'sync-runs'],
    queryFn: () =>
      client.get<{ items: SyncRun[] }>(`/api/v1/connections/${connectionId}/sync-runs`, {
        params: { limit: 10 },
      }).then(res => res.data),
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (error) {
    return <div className="text-red-500 text-sm">Failed to load sync runs</div>
  }

  const runs = data?.items || []

  if (runs.length === 0) {
    return <div className="text-gray-500 text-sm">No sync runs yet</div>
  }

  return (
    <div className="border rounded-md divide-y overflow-hidden">
      {runs.map((run) => (
        <div key={run.id} className="p-3 flex items-center justify-between bg-white text-sm">
          <div className="flex items-center gap-3">
            <StatusBadge status={run.status} />
            <div className="flex flex-col">
              <span className="text-gray-900 font-medium">
                {new Date(run.started_at).toLocaleString()}
              </span>
              <span className="text-gray-500 text-xs">
                {run.completed_at ? `Completed ${new Date(run.completed_at).toLocaleTimeString()}` : 'In progress'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-right">
            <div className="flex flex-col">
              <span className="text-gray-900 font-medium">{run.accounts_synced} accounts</span>
              {run.error_code && (
                <span className="text-red-500 text-xs font-mono">{run.error_code}</span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
