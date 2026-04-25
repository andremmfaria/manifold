import { useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmRuleBuilder } from '@/features/alarms/AlarmRuleBuilder'
import { useCreateAlarm } from '@/features/alarms/useAlarms'
import { useAccounts } from '@/features/accounts/useAccounts'
import { useNotifiers } from '@/features/notifiers/useNotifiers'
import { rootRoute } from '../__root'

export const alarmsNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/alarms/new',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: NewAlarmPage,
})

function NewAlarmPage() {
  const navigate = useNavigate()
  const { mutateAsync: createAlarm, isPending } = useCreateAlarm()
  const { data: accounts } = useAccounts()
  const { data: notifiers } = useNotifiers()

  const [name, setName] = useState('')
  const [accountIds, setAccountIds] = useState<string[]>([])
  const [notifierIds, setNotifierIds] = useState<string[]>([])
  
  // Default rule structure expected by react-querybuilder
  const [condition, setCondition] = useState({
    combinator: 'and',
    rules: [
      { field: 'balance', operator: '<', value: 100 }
    ]
  })

  const [repeatCount, setRepeatCount] = useState(1)
  const [forDurationMinutes, setForDurationMinutes] = useState(0)
  const [cooldownMinutes, setCooldownMinutes] = useState(60)
  const [notifyOnResolve, setNotifyOnResolve] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    try {
      if (!name) throw new Error("Name is required");
      if (accountIds.length === 0) throw new Error("At least one account is required");

      await createAlarm({
        name,
        condition,
        account_ids: accountIds,
        notifier_ids: notifierIds,
        repeat_count: repeatCount,
        for_duration_minutes: forDurationMinutes,
        cooldown_minutes: cooldownMinutes,
        notify_on_resolve: notifyOnResolve
      })
      navigate({ to: '/alarms' })
    } catch (err: any) {
      setError(err.message || 'Failed to create alarm')
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-3xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Create Alarm</h1>
          <p className="mt-1 text-slate-500">Define conditions for automated alerts.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-8 bg-white p-6 rounded-xl border shadow-sm">
          {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-md">{error}</div>}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Alarm Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                placeholder="e.g. Low Balance Alert"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Accounts to Monitor</label>
              <select
                multiple
                value={accountIds}
                onChange={e => setAccountIds(Array.from(e.target.selectedOptions, option => option.value))}
                className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border h-32"
              >
                {accounts?.map(acc => (
                  <option key={acc.id} value={acc.id}>{acc.display_name || acc.account_type}</option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">Hold Ctrl/Cmd to select multiple</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Trigger Condition</label>
              <AlarmRuleBuilder value={condition} onChange={setCondition} />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Notifiers (Optional)</label>
              <select
                multiple
                value={notifierIds}
                onChange={e => setNotifierIds(Array.from(e.target.selectedOptions, option => option.value))}
                className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border h-32"
              >
                {notifiers?.items.map(notifier => (
                  <option key={notifier.id} value={notifier.id}>{notifier.name} ({notifier.type})</option>
                ))}
              </select>
            </div>

            <div className="border-t pt-4">
              <h3 className="text-sm font-semibold mb-4 text-slate-800">Advanced Settings</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Required consecutive matches (Repeat Count)</label>
                  <input
                    type="number"
                    min="1"
                    value={repeatCount}
                    onChange={e => setRepeatCount(parseInt(e.target.value))}
                    className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">For duration (minutes)</label>
                  <input
                    type="number"
                    min="0"
                    value={forDurationMinutes}
                    onChange={e => setForDurationMinutes(parseInt(e.target.value))}
                    className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Cooldown (minutes)</label>
                  <input
                    type="number"
                    min="0"
                    value={cooldownMinutes}
                    onChange={e => setCooldownMinutes(parseInt(e.target.value))}
                    className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
                  />
                </div>
                
                <div className="flex items-center pt-6">
                  <input
                    type="checkbox"
                    id="notify_on_resolve"
                    checked={notifyOnResolve}
                    onChange={e => setNotifyOnResolve(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="notify_on_resolve" className="ml-2 block text-sm text-slate-700">
                    Notify when resolved
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={() => navigate({ to: '/alarms' })}
              className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
            >
              {isPending ? 'Saving...' : 'Create Alarm'}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  )
}
