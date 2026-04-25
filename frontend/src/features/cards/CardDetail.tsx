export function CardDetail({ card }: { card: any }) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <h2 className="text-xl font-semibold">{card.display_name || 'Card detail'}</h2>
      <dl className="mt-4 grid gap-3 text-sm">
        <div className="flex justify-between gap-3"><dt>Network</dt><dd>{card.card_network || '—'}</dd></div>
        <div className="flex justify-between gap-3"><dt>Last digits</dt><dd>{card.partial_card_number || '—'}</dd></div>
        <div className="flex justify-between gap-3"><dt>Currency</dt><dd>{card.currency || '—'}</dd></div>
        <div className="flex justify-between gap-3"><dt>Credit limit</dt><dd>{card.credit_limit || '—'}</dd></div>
      </dl>
    </div>
  )
}
