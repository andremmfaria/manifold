export function DirectDebitList({ items }: { items: any[] }) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 border-b pb-3 last:border-b-0">
            <div>
              <p className="font-medium">{item.name}</p>
              <p className="text-sm text-slate-500">{item.reference || 'No reference'}</p>
            </div>
            <div className="text-right text-sm">
              <p>{item.amount || '—'} {item.currency || ''}</p>
              <p className="text-slate-500">{item.status || 'unknown'}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
