import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'

type Props = { accountId: string; onChange: (next: string) => void }

export function TransactionFilters({ accountId, onChange }: Props) {
  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              className="pl-8"
              defaultValue={accountId}
              onChange={(event) => onChange(event.target.value)}
              placeholder="Filter by account ID…"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
