import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function StandingOrderList({ items }: { items: any[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No standing orders found for this account.
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Reference</TableHead>
          <TableHead>Frequency</TableHead>
          <TableHead>Next Amount</TableHead>
          <TableHead>Next Date</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="font-medium text-foreground">
              {item.reference || 'Standing order'}
            </TableCell>
            <TableCell className="text-muted-foreground capitalize">
              {item.frequency || '—'}
            </TableCell>
            <TableCell className="text-foreground">
              {item.next_payment_amount
                ? `${item.next_payment_amount} ${item.currency || ''}`.trim()
                : '—'}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {item.next_payment_date || '—'}
            </TableCell>
            <TableCell>
              {item.status ? (
                <Badge variant="secondary" className="capitalize">
                  {item.status}
                </Badge>
              ) : (
                <span className="text-muted-foreground text-xs">—</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
