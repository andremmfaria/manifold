import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'

export function CardList({ items }: { items: any[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {items.map((item) => (
        <Card key={item.id}>
          <CardHeader>
            <CardTitle>{item.display_name || 'Card'}</CardTitle>
            <CardDescription>{item.card_network || 'Unknown network'}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold tracking-widest text-foreground">
              •••• {item.partial_card_number || '----'}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
