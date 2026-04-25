import type { Account } from '@/api/accounts'

export function AccountCard({ account }: { account: Account }) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <h3 className="font-semibold">{account.display_name || account.account_type}</h3>
      <p className="mt-1 text-sm text-slate-500">{account.account_type}</p>
      <p className="mt-4 text-2xl font-semibold">
        {account.current_balance || '—'} {account.balance_currency || account.currency}
      </p>
    </div>
  )
}
