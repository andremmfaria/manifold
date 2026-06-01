import type { ColumnDef } from '@tanstack/react-table'
import { useQuery } from '@tanstack/react-query'
import { getAlarmHistory } from '@/api/alarms'
import { AlarmStateBadge } from './AlarmStateBadge'
import { Badge } from '@/components/ui/badge'
import { DataTable } from '@/components/ui/data-table'

const columns: ColumnDef<any, any>[] = [
  {
    id: 'evaluated_at',
    accessorKey: 'evaluated_at',
    meta: { label: 'Evaluated At' },
    header: 'Evaluated At',
    cell: ({ row }) => (
      <span className="text-foreground">
        {new Date(row.original.evaluated_at).toLocaleString()}
      </span>
    ),
  },
  {
    id: 'result',
    accessorKey: 'result',
    meta: { label: 'Result' },
    header: 'Result',
    cell: ({ row }) => (
      <Badge
        variant={row.original.result === 'PASS' ? 'outline' : 'destructive'}
        className={
          row.original.result === 'PASS'
            ? 'border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400'
            : undefined
        }
      >
        {row.original.result}
      </Badge>
    ),
  },
  {
    id: 'state_transition',
    accessorKey: 'previous_state',
    meta: { label: 'State Transition' },
    header: 'State Transition',
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <AlarmStateBadge state={row.original.previous_state} />
        <span className="text-muted-foreground">→</span>
        <AlarmStateBadge state={row.original.new_state} />
      </div>
    ),
  },
  {
    id: 'explanation',
    accessorKey: 'explanation',
    meta: { label: 'Explanation' },
    header: 'Explanation',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.explanation || '—'}</span>
    ),
  },
]

export function AlarmHistory({ alarmId }: { alarmId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['alarms', alarmId, 'history'],
    queryFn: () => getAlarmHistory(alarmId),
  })

  if (isLoading) return <div className="text-sm text-muted-foreground">Loading history...</div>
  if (!data?.items?.length)
    return <div className="text-sm text-muted-foreground">No history available</div>

  return <DataTable columns={columns} data={data.items} storageKey="alarm-history" />
}
