import type { ColumnDef } from '@tanstack/react-table'
import { Link } from '@tanstack/react-router'
import { Card, CardTitle, CardContent } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'

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

const columns: ColumnDef<any, any>[] = [
  {
    id: 'date',
    accessorKey: 'transaction_date',
    meta: { label: 'Date' },
    header: 'Date',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.transaction_date || '—'}</span>
    ),
  },
  {
    id: 'account',
    accessorKey: 'account_id',
    meta: { label: 'Account' },
    header: 'Account',
    cell: ({ row }) => {
      const { account_id, account_display_name } = row.original
      if (!account_id) return <span className="text-muted-foreground">—</span>
      const label = account_display_name || account_id
      const isRawId = !account_display_name
      return (
        <Link
          to="/accounts/$accountId"
          params={{ accountId: account_id }}
          className="rounded-sm outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className={isRawId ? 'font-mono text-xs' : 'font-medium'}>{label}</span>
        </Link>
      )
    },
  },
  {
    id: 'description',
    accessorKey: 'description',
    meta: { label: 'Description' },
    header: 'Description',
    cell: ({ row }) => (
      <span className="font-medium text-foreground">{row.original.description || '—'}</span>
    ),
  },
  {
    id: 'merchant',
    accessorKey: 'merchant_name',
    meta: { label: 'Merchant' },
    header: 'Merchant',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.merchant_name || '—'}</span>
    ),
  },
  {
    id: 'amount',
    accessorKey: 'amount',
    meta: { label: 'Amount' },
    header: () => <div className="text-right">Amount</div>,
    cell: ({ row }) => (
      <div className="text-right">
        <AmountCell amount={row.original.amount} currency={row.original.currency} />
      </div>
    ),
  },
]

export function TransactionTable({ items }: { items: any[] }) {
  return (
    <Card>
      <CardContent className="p-4">
        <DataTable
          columns={columns}
          data={items}
          emptyMessage="No transactions found."
          storageKey="tx-table"
          toolbar={<CardTitle>Transactions</CardTitle>}
        />
      </CardContent>
    </Card>
  )
}
