import { Bell, AlertTriangle } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function AlarmStatusWidget({ activeAlarmsCount }: { activeAlarmsCount: number }) {
  const hasAlarms = activeAlarmsCount > 0
  return (
    <Card className={hasAlarms ? 'ring-1 ring-destructive/30' : undefined}>
      <CardHeader>
        <div className="flex items-center gap-2">
          {hasAlarms ? (
            <AlertTriangle className="h-4 w-4 text-destructive" />
          ) : (
            <Bell className="h-4 w-4 text-muted-foreground" />
          )}
          <CardTitle className={hasAlarms ? 'text-destructive' : undefined}>
            Active Alarms
          </CardTitle>
          {hasAlarms && (
            <Badge variant="destructive" className="ml-auto">{activeAlarmsCount}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <span className={`text-4xl font-bold tracking-tight ${hasAlarms ? 'text-destructive' : 'text-foreground'}`}>
          {activeAlarmsCount}
        </span>
        <p className={`mt-1 text-sm ${hasAlarms ? 'text-destructive/80' : 'text-muted-foreground'}`}>
          {activeAlarmsCount === 1 ? 'Alarm requires attention' : 'Alarms require attention'}
        </p>
      </CardContent>
    </Card>
  )
}
