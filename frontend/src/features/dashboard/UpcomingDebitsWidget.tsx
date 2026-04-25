import { Calendar } from 'lucide-react'
import type { DashboardSummary } from '@/types/dashboard'

export function UpcomingDebitsWidget({ debits }: { debits: DashboardSummary['upcoming_debits'] }) {
  if (!debits?.length) return null;

  return (
    <div className="rounded-xl border bg-white shadow-sm overflow-hidden mt-6">
      <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
        <h3 className="font-semibold text-slate-800">Upcoming Predicted Debits</h3>
      </div>
      <div className="divide-y divide-slate-100">
        {debits.map((debit, i) => (
          <div key={i} className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Calendar className="h-5 w-5 text-slate-400" />
              <div>
                <p className="text-sm font-medium text-slate-900">
                  {debit.label || 'Recurring Debit'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  Expected: {new Date(debit.next_predicted_at).toLocaleDateString()}
                  {debit.confidence && ` (${Math.round(debit.confidence * 100)}% confidence)`}
                </p>
              </div>
            </div>
            <div className="text-right">
              {debit.amount_mean && (
                <p className="text-sm font-bold text-slate-900">
                  ~${Math.abs(parseFloat(debit.amount_mean)).toFixed(2)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
