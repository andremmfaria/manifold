import { CreditCard, GitMerge, Unlink } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import type { Account } from '@/api/accounts'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

type Props = {
  account: Account
  /** When truthy, the card renders a selection checkbox. */
  selectionMode?: boolean
  selected?: boolean
  onToggleSelect?: (id: string) => void
  /** Whether this account is the master (primary) in its identity group. */
  isMaster?: boolean
  /** Whether this account belongs to a multi-member identity group (i.e. is merged). */
  isMerged?: boolean
  onUnmerge?: (account: Account) => void
}

export function AccountCard({
  account,
  selectionMode,
  selected,
  onToggleSelect,
  isMaster,
  isMerged,
  onUnmerge,
}: Props) {
  const balance = account.current_balance
  const currency = account.balance_currency || account.currency

  return (
    <Card
      className={cn(
        'relative transition-colors',
        selected && 'ring-2 ring-primary',
        isMerged && !selected && 'ring-1 ring-primary/30',
      )}
    >
      {/* Selection checkbox overlay */}
      {selectionMode && (
        <div className="absolute top-3 left-3 z-10">
          <Checkbox
            checked={selected}
            onCheckedChange={() => onToggleSelect?.(account.id)}
            aria-label={`Select ${account.display_name || account.account_type}`}
          />
        </div>
      )}

      <CardHeader className={cn(selectionMode && 'pl-10')}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <CreditCard className="h-4 w-4 text-muted-foreground shrink-0" />
            <CardTitle className="truncate">
              <Link
                to="/accounts/$accountId"
                params={{ accountId: account.id }}
                className="rounded-sm outline-none hover:underline focus-visible:underline focus-visible:ring-2 focus-visible:ring-ring"
              >
                {account.display_name || account.account_type}
              </Link>
            </CardTitle>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {isMerged && (
              <Badge
                variant="outline"
                className="gap-1 border-primary/40 bg-primary/5 text-primary text-xs"
              >
                <GitMerge className="h-3 w-3" aria-hidden="true" />
                {isMaster ? 'Primary' : 'Linked'}
              </Badge>
            )}
            <Badge variant="outline" className="capitalize">
              {account.account_type.replace(/_/g, ' ')}
            </Badge>
          </div>
        </div>
        <CardDescription className="font-mono text-xs">{account.id}</CardDescription>
      </CardHeader>

      <CardContent className="flex items-end justify-between gap-2">
        <p className="text-3xl font-bold tracking-tight text-foreground">
          {balance != null ? (
            <>
              {parseFloat(balance).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              <span className="ml-1.5 text-base font-medium text-muted-foreground">{currency}</span>
            </>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </p>

        {isMerged && !selectionMode && onUnmerge && (
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground gap-1.5 shrink-0"
            onClick={() => onUnmerge(account)}
            aria-label={`Unmerge ${account.display_name || account.account_type}`}
          >
            <Unlink className="h-3.5 w-3.5" />
            Unmerge
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
