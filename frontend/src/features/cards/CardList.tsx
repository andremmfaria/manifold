export function CardList({ items }: { items: any[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {items.map((item) => (
        <div key={item.id} className="rounded-xl border bg-white p-4 shadow-sm">
          <h3 className="font-semibold">{item.display_name || 'Card'}</h3>
          <p className="mt-1 text-sm text-slate-500">{item.card_network || 'Unknown network'}</p>
          <p className="mt-4 text-lg font-semibold">•••• {item.partial_card_number || '----'}</p>
        </div>
      ))}
    </div>
  )
}
