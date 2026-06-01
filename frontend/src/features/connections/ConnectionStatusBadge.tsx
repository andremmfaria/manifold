import { Badge } from '@/components/ui/badge'

export function ConnectionStatusBadge({ status }: { status: string }) {
  const className =
    status === 'active'
      ? 'bg-emerald-600/15 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400 border-transparent'
      : status === 'error'
        ? undefined
        : 'bg-muted text-muted-foreground border-transparent'

  const variant = status === 'error' ? 'destructive' : 'outline'

  return (
    <Badge variant={variant} className={className}>
      {status}
    </Badge>
  )
}
