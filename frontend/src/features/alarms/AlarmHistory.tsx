import { useQuery } from '@tanstack/react-query'
import { getAlarmHistory } from '@/api/alarms'
import { AlarmStateBadge } from './AlarmStateBadge'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function AlarmHistory({ alarmId }: { alarmId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['alarms', alarmId, 'history'],
    queryFn: () => getAlarmHistory(alarmId),
  })

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading history...</div>
  if (!data?.items?.length) return <div className="text-sm text-muted-foreground">No history available</div>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Evaluated At</TableHead>
          <TableHead>Result</TableHead>
          <TableHead>State Transition</TableHead>
          <TableHead>Explanation</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((item, i) => (
          <TableRow key={i}>
            <TableCell className="text-foreground">
              {new Date(item.evaluated_at).toLocaleString()}
            </TableCell>
            <TableCell>
              <Badge
                variant={item.result === 'PASS' ? 'outline' : 'destructive'}
                className={item.result === 'PASS' ? 'border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400' : undefined}
              >
                {item.result}
              </Badge>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <AlarmStateBadge state={item.previous_state} />
                <span className="text-muted-foreground">→</span>
                <AlarmStateBadge state={item.new_state} />
              </div>
            </TableCell>
            <TableCell className="text-muted-foreground">
              {item.explanation || '—'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
