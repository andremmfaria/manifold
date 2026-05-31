import { CreditCard } from 'lucide-react'
import type { Account } from '@/api/accounts'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function AccountCard({ account }: { account: Account }) {
  const balance = account.current_balance
  const currency = account.balance_currency || account.currency

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <CreditCard className="h-4 w-4 text-muted-foreground shrink-0" />
            <CardTitle className="truncate">
              {account.display_name || account.account_type}
            </CardTitle>
          </div>
          <Badge variant="outline" className="shrink-0 capitalize">
            {account.account_type.replace(/_/g, ' ')}
          </Badge>
        </div>
        <CardDescription className="font-mono text-xs">{account.id}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold tracking-tight text-foreground">
          {balance != null ? (
            <>
              {parseFloat(balance).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              <span className="ml-1.5 text-base font-medium text-muted-foreground">
                {currency}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </p>
      </CardContent>
    </Card>
  )
}
