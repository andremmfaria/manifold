import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function AmountCell({ amount, currency }: { amount: string | null; currency: string | null }) {
  if (!amount) return <span className="text-muted-foreground">—</span>
  const value = parseFloat(amount)
  const isNegative = value < 0
  return (
    <span
      className={
        isNegative
          ? 'text-destructive dark:text-red-400 font-medium tabular-nums'
          : 'text-emerald-600 dark:text-emerald-400 font-medium tabular-nums'
      }
    >
      {value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      {currency ? <span className="ml-1 text-muted-foreground font-normal">{currency}</span> : null}
    </span>
  )
}

export function TransactionTable({ items }: { items: any[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Transactions</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="px-4">Date</TableHead>
              <TableHead className="px-4">Description</TableHead>
              <TableHead className="px-4">Merchant</TableHead>
              <TableHead className="px-4 text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                  No transactions found.
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="px-4 text-muted-foreground">
                    {item.transaction_date || '—'}
                  </TableCell>
                  <TableCell className="px-4 font-medium text-foreground">
                    {item.description || '—'}
                  </TableCell>
                  <TableCell className="px-4 text-muted-foreground">
                    {item.merchant_name || '—'}
                  </TableCell>
                  <TableCell className="px-4 text-right">
                    <AmountCell amount={item.amount} currency={item.currency} />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
