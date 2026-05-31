import { DollarSign } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

export function BalanceSummaryCard({ accountsTotal }: { accountsTotal: number }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2 text-muted-foreground">
          <DollarSign className="h-4 w-4" />
          <CardTitle>Total Accounts Balance</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <span className="text-4xl font-bold tracking-tight text-foreground">
          ${accountsTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </CardContent>
    </Card>
  )
}
