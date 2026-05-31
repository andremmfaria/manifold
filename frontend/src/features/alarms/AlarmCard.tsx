import type { Alarm } from '@/types/alarm'
import { AlarmStateBadge } from './AlarmStateBadge'
import { BellOff, BellRing } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function AlarmCard({ alarm, onMute, onUnmute }: { alarm: Alarm; onMute?: () => void; onUnmute?: () => void }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="font-semibold text-foreground">{alarm.name}</h3>
            <AlarmStateBadge state={alarm.state} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Last evaluated: {alarm.last_evaluated_at ? new Date(alarm.last_evaluated_at).toLocaleString() : 'Never'}
          </p>
        </div>
        <div>
          {alarm.state === 'muted' ? (
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onUnmute?.(); }}
            >
              <BellRing className="h-4 w-4" />
              Unmute
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); onMute?.(); }}
            >
              <BellOff className="h-4 w-4" />
              Mute
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
