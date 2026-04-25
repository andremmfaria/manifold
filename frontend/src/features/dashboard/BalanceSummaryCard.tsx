import { DollarSign } from 'lucide-react'

export function BalanceSummaryCard({ accountsTotal }: { accountsTotal: number }) {
  return (
    <div className="rounded-xl border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3 text-slate-500">
        <DollarSign className="h-5 w-5" />
        <h3 className="font-medium">Total Accounts Balance</h3>
      </div>
      <div className="mt-4">
        <span className="text-4xl font-bold tracking-tight text-slate-900">
          ${accountsTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>
    </div>
  )
}
