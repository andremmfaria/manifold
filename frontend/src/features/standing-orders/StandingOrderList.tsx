export function StandingOrderList({ items }: { items: any[] }) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <ul className="space-y-3">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 border-b pb-3 last:border-b-0">
            <div>
              <p className="font-medium">{item.reference || 'Standing order'}</p>
              <p className="text-sm text-slate-500">{item.frequency || 'No frequency'}</p>
            </div>
            <div className="text-right text-sm">
              <p>{item.next_payment_amount || '—'} {item.currency || ''}</p>
              <p className="text-slate-500">{item.next_payment_date || 'No date'}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
