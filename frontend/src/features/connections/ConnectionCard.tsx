import type { Connection } from '@/api/connections'
import { ConnectionStatusBadge } from './ConnectionStatusBadge'
import { Card, CardHeader, CardTitle, CardDescription, CardAction, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function ConnectionCard({ connection, onSync }: { connection: Connection; onSync?: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{connection.display_name || connection.provider_type}</CardTitle>
        <CardDescription>{connection.provider_type}</CardDescription>
        <CardAction>
          <ConnectionStatusBadge status={connection.status} />
        </CardAction>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-2 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Auth</dt>
            <dd className="text-foreground">{connection.auth_status}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Consent</dt>
            <dd className="text-foreground">{connection.consent_expires_at || '—'}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Last sync</dt>
            <dd className="text-foreground">{connection.last_sync_at || 'Never'}</dd>
          </div>
        </dl>
      </CardContent>
      {onSync ? (
        <CardFooter>
          <Button variant="outline" size="sm" onClick={onSync} type="button">
            Run sync
          </Button>
        </CardFooter>
      ) : null}
    </Card>
  )
}
