import { RefreshCcw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function SyncStatusWidget({ lastSyncAt }: { lastSyncAt: string | null }) {
  const syncDate = lastSyncAt ? new Date(lastSyncAt) : null
  // Stale if last sync was more than 24h ago
  const isStale = syncDate ? new Date().getTime() - syncDate.getTime() > 1000 * 60 * 60 * 24 : true

  return (
    <Card className={isStale && lastSyncAt ? 'ring-1 ring-yellow-400/40' : undefined}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <RefreshCcw
            className={`h-4 w-4 ${isStale && lastSyncAt ? 'text-yellow-600 dark:text-yellow-400' : 'text-muted-foreground'}`}
          />
          <CardTitle
            className={isStale && lastSyncAt ? 'text-yellow-700 dark:text-yellow-300' : undefined}
          >
            Last Sync
          </CardTitle>
          {isStale && lastSyncAt && (
            <Badge
              variant="outline"
              className="ml-auto border-yellow-400/50 text-yellow-700 dark:text-yellow-300"
            >
              Stale
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <span
          className={`text-xl font-semibold tracking-tight ${isStale && lastSyncAt ? 'text-yellow-700 dark:text-yellow-300' : 'text-foreground'}`}
        >
          {syncDate ? syncDate.toLocaleString() : 'Never'}
        </span>
        {isStale && lastSyncAt && (
          <p className="mt-1 text-sm text-yellow-600 dark:text-yellow-400">Data may be stale</p>
        )}
      </CardContent>
    </Card>
  )
}
