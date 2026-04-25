export function TransactionTable({ items }: { items: any[] }) {
  return (
    <div className="overflow-hidden rounded-xl border bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left">Date</th>
            <th className="px-4 py-3 text-left">Description</th>
            <th className="px-4 py-3 text-left">Merchant</th>
            <th className="px-4 py-3 text-right">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="px-4 py-3">{item.transaction_date || '—'}</td>
              <td className="px-4 py-3">{item.description || '—'}</td>
              <td className="px-4 py-3">{item.merchant_name || '—'}</td>
              <td className="px-4 py-3 text-right">
                {item.amount || '—'} {item.currency || ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
