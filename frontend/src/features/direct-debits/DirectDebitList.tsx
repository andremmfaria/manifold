import type { ColumnDef } from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'
import { CardTitle } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'

const columns: ColumnDef<any, any>[] = [
  {
    id: 'name',
    accessorKey: 'name',
    meta: { label: 'Name' },
    header: 'Name',
    cell: ({ row }) => <span className="font-medium text-foreground">{row.original.name}</span>,
  },
  {
    id: 'reference',
    accessorKey: 'reference',
    meta: { label: 'Reference' },
    header: 'Reference',
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.reference || '—'}</span>
    ),
  },
  {
    id: 'amount',
    accessorKey: 'amount',
    meta: { label: 'Amount' },
    header: 'Amount',
    cell: ({ row }) => (
      <span className="text-foreground">
        {row.original.amount ? `${row.original.amount} ${row.original.currency || ''}`.trim() : '—'}
      </span>
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
        <span className="text-muted-foreground text-xs">unknown</span>
      ),
  },
]

export function DirectDebitList({ items }: { items: any[] }) {
  return (
    <DataTable
      columns={columns}
      data={items}
      emptyMessage="No direct debits found for this account."
      storageKey="direct-debits"
      toolbar={<CardTitle>All Direct Debits</CardTitle>}
    />
  )
}
