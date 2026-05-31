import { Clock } from 'lucide-react'
import type { DashboardSummary } from '@/types/dashboard'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

export function RecentTransactionsFeed({ events }: { events: DashboardSummary['recent_events'] }) {
  if (!events?.length) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Clock className="h-10 w-10 text-muted-foreground/30 mb-3" />
          <p className="text-muted-foreground">No recent activity detected.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Event</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Account</TableHead>
              <TableHead className="text-right">Time</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((event, i) => (
              <TableRow key={i}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
                    <span className="font-medium">
                      {event.event_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{event.source_type}</TableCell>
                <TableCell className="font-mono text-muted-foreground">
                  {event.account_id.substring(0, 8)}&hellip;
                </TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {new Date(event.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
