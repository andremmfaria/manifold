import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export function DirectDebitList({ items }: { items: any[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No direct debits found for this account.
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Reference</TableHead>
          <TableHead>Amount</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="font-medium text-foreground">{item.name}</TableCell>
            <TableCell className="text-muted-foreground">{item.reference || '—'}</TableCell>
            <TableCell className="text-foreground">
              {item.amount ? `${item.amount} ${item.currency || ''}`.trim() : '—'}
            </TableCell>
            <TableCell>
              {item.status ? (
                <Badge variant="secondary" className="capitalize">
                  {item.status}
                </Badge>
              ) : (
                <span className="text-muted-foreground text-xs">unknown</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
