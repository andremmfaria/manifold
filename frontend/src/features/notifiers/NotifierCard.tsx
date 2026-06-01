import type { Notifier } from '@/types/notifier'
import { Bell, Activity, Send } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

export function NotifierCard({
  notifier,
  onTest,
  isTesting = false,
}: {
  notifier: Notifier
  onTest?: () => void
  isTesting?: boolean
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex items-start gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
            <Bell className="h-5 w-5 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-foreground">{notifier.name}</h3>
              <Badge variant="secondary" className="uppercase tracking-wide">
                {notifier.type}
              </Badge>
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              <span
                className={`inline-flex h-2 w-2 rounded-full ${notifier.is_enabled ? 'bg-green-500' : 'bg-muted-foreground/40'}`}
              />
              {notifier.is_enabled ? 'Active' : 'Disabled'}
            </div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onTest}
          disabled={isTesting || !notifier.is_enabled}
        >
          {isTesting ? <Activity className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          Test
        </Button>
      </CardContent>
    </Card>
  )
}
