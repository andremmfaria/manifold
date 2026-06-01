import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const stateVariantMap: Record<
  string,
  { variant: 'default' | 'secondary' | 'destructive' | 'outline'; extra?: string }
> = {
  ok: {
    variant: 'outline',
    extra: 'border-green-500/50 bg-green-500/10 text-green-600 dark:text-green-400',
  },
  pending: {
    variant: 'outline',
    extra: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
  },
  firing: { variant: 'destructive' },
  resolved: { variant: 'outline', extra: 'border-primary/50 bg-primary/10 text-primary' },
  muted: { variant: 'secondary' },
}

export function AlarmStateBadge({ state }: { state: string }) {
  const mapping = stateVariantMap[state] ?? { variant: 'secondary' as const }
  return (
    <Badge variant={mapping.variant} className={cn(mapping.extra)}>
      {state.toUpperCase()}
    </Badge>
  )
}
