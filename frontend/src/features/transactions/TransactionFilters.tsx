type Props = { accountId: string; onChange: (next: string) => void }

export function TransactionFilters({ accountId, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-4">
      <input
        className="rounded border px-3 py-2"
        defaultValue={accountId}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Filter by account id"
      />
    </div>
  )
}
