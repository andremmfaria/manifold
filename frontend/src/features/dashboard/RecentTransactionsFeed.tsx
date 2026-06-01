import { useMemo, useState } from 'react'
import { Clock } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import type { ColumnDef } from '@tanstack/react-table'
import type { DashboardSummary } from '@/types/dashboard'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { DateRangeFilter, inRange, lastNDays } from '@/components/DateRangeFilter'
import { useAccounts } from '@/features/accounts/useAccounts'
import { useConnections } from '@/features/connections/useConnections'

type RecentEvent = DashboardSummary['recent_events'][number]

const linkClassName =
  'rounded-sm outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring'

export function RecentTransactionsFeed({ events }: { events: DashboardSummary['recent_events'] }) {
  const [range, setRange] = useState(() => lastNDays(30))

  const { data: accounts } = useAccounts()
  const { data: connections } = useConnections()

  const accountMap = useMemo(
    () => new Map((accounts ?? []).map((a) => [a.id, a.display_name ?? a.id])),
    [accounts],
  )
  const connectionMap = useMemo(
    () => new Map((connections ?? []).map((c) => [c.id, c.display_name ?? c.id])),
    [connections],
  )

  const columns = useMemo<ColumnDef<RecentEvent, any>[]>(
    () => [
      {
        id: 'event',
        accessorKey: 'event_type',
        meta: { label: 'Event' },
        header: 'Event',
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
            <span className="font-medium">
              {row.original.event_type.replace(/_/g, ' ').toUpperCase()}
            </span>
          </div>
        ),
      },
      {
        id: 'source',
        accessorKey: 'source_type',
        meta: { label: 'Source' },
        header: 'Source',
        cell: ({ row }) => {
          const { connection_id, source_type } = row.original
          if (!connection_id) {
            return <span className="text-muted-foreground">{source_type}</span>
          }
          const label = connectionMap.get(connection_id) ?? connection_id
          return (
            <Link
              to="/connections/$connectionId"
              params={{ connectionId: connection_id }}
              className={linkClassName}
            >
              <span className="text-sm text-muted-foreground">{label}</span>
            </Link>
          )
        },
      },
      {
        id: 'account',
        accessorKey: 'account_id',
        meta: { label: 'Account' },
        header: 'Account',
        cell: ({ row }) => {
          const { account_id } = row.original
          if (!account_id) return <span className="text-muted-foreground">—</span>
          const label = accountMap.get(account_id) ?? account_id
          return (
            <Link
              to="/accounts/$accountId"
              params={{ accountId: account_id }}
              className={linkClassName}
            >
              <span className="text-sm text-muted-foreground">{label}</span>
            </Link>
          )
        },
      },
      {
        id: 'time',
        accessorKey: 'occurred_at',
        meta: { label: 'Time' },
        header: () => <div className="text-right">Time</div>,
        cell: ({ row }) => (
          <div className="text-right text-muted-foreground">
            {new Date(row.original.occurred_at).toLocaleString([], {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        ),
      },
    ],
    [accountMap, connectionMap],
  )

  const filtered = useMemo(
    () => (events ?? []).filter((event) => inRange(event.occurred_at, range)),
    [events, range],
  )

  const emptyMessage = (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <Clock className="h-10 w-10 text-muted-foreground/30 mb-3" />
      <p className="text-muted-foreground">
        {events?.length ? 'No activity in the selected range.' : 'No recent activity detected.'}
      </p>
    </div>
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>Recent Activity</CardTitle>
          <DateRangeFilter range={range} onChange={setRange} idPrefix="activity" />
        </div>
      </CardHeader>
      <CardContent className="p-4">
        <DataTable
          columns={columns}
          data={filtered}
          emptyMessage={emptyMessage}
          storageKey="recent-activity"
        />
      </CardContent>
    </Card>
  )
}
