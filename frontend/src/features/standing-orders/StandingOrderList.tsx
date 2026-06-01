import type { ColumnDef } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import { CardTitle } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'

const columns: ColumnDef<any, any>[] = [
  {
    id: 'reference',
    accessorKey: 'reference',
    meta: { label: 'Reference' },
    header: 'Reference',
    cell: ({ row }) => (
      <span className="font-medium text-foreground">
        {row.original.reference || 'Standing order'}
      </span>
    ),
  },
  {
    id: 'frequency',
    accessorKey: 'frequency',
    meta: { label: 'Frequency' },
    header: 'Frequency',
    cell: ({ row }) => (
      <span className="text-muted-foreground capitalize">{row.original.frequency || '—'}</span>
    ),
  },
  {
    id: 'next_amount',
    accessorKey: 'next_payment_amount',
    meta: { label: 'Next Amount' },
    header: 'Next Amount',
    cell: ({ row }) => (
      <span className="text-foreground">
        {row.original.next_payment_amount
          ? `${row.original.next_payment_amount} ${row.original.currency || ''}`.trim()
          : '—'}
      </span>
    ),
  },
  {
    id: 'next_date',
    accessorKey: 'next_payment_date',
    meta: { label: 'Next Date' },
    header: 'Next Date',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.next_payment_date || '—'}</span>
    ),
  },
  {
    id: 'status',
    accessorKey: 'status',
    meta: { label: 'Status' },
    header: 'Status',
    cell: ({ row }) =>
      row.original.status ? (
        <Badge variant="secondary" className="capitalize">
          {row.original.status}
        </Badge>
      ) : (
        <span className="text-muted-foreground text-xs">—</span>
      ),
  },
]

export function StandingOrderList({ items }: { items: any[] }) {
  return (
    <DataTable
      columns={columns}
      data={items}
      emptyMessage="No standing orders found for this account."
      storageKey="standing-orders"
      toolbar={<CardTitle>All Standing Orders</CardTitle>}
    />
  )
}
