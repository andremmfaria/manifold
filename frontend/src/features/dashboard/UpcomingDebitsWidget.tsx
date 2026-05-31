import { Calendar } from 'lucide-react'
import type { DashboardSummary } from '@/types/dashboard'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function UpcomingDebitsWidget({ debits }: { debits: DashboardSummary['upcoming_debits'] }) {
  if (!debits?.length) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upcoming Predicted Debits</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-border">
          {debits.map((debit, i) => (
            <div key={i} className="flex items-center justify-between p-4 gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">
                    {debit.label || 'Recurring Debit'}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {new Date(debit.next_predicted_at).toLocaleDateString()}
                    {debit.confidence && (
                      <Badge variant="secondary" className="ml-1.5 text-xs">
                        {Math.round(debit.confidence * 100)}%
                      </Badge>
                    )}
                  </p>
                </div>
              </div>
              {debit.amount_mean && (
                <span className="text-sm font-bold text-foreground shrink-0">
                  ~${Math.abs(parseFloat(debit.amount_mean)).toFixed(2)}
                </span>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
