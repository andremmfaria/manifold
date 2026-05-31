import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

export function CardDetail({ card }: { card: any }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{card.display_name || 'Card detail'}</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Network</dt>
            <dd className="text-foreground">{card.card_network || '—'}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Last digits</dt>
            <dd className="text-foreground">{card.partial_card_number || '—'}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Currency</dt>
            <dd className="text-foreground">{card.currency || '—'}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted-foreground">Credit limit</dt>
            <dd className="text-foreground">{card.credit_limit || '—'}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
