import { useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { AlarmRuleBuilder } from '@/features/alarms/AlarmRuleBuilder'
import { useCreateAlarm } from '@/features/alarms/useAlarms'
import { useAccounts } from '@/features/accounts/useAccounts'
import { useNotifiers } from '@/features/notifiers/useNotifiers'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
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
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Create Alarm</h1>
          <p className="mt-1 text-muted-foreground">Define conditions for automated alerts.</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Alarm Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg border border-destructive/20">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="alarm-name">Alarm Name</Label>
                <Input
                  id="alarm-name"
                  type="text"
                  required
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Low Balance Alert"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="alarm-accounts">Accounts to Monitor</Label>
                <select
                  id="alarm-accounts"
                  multiple
                  value={accountIds}
                  onChange={e => setAccountIds(Array.from(e.target.selectedOptions, option => option.value))}
                  className="h-32 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm text-foreground focus-visible:outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {accounts?.map(acc => (
                    <option key={acc.id} value={acc.id}>{acc.display_name || acc.account_type}</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">Hold Ctrl/Cmd to select multiple</p>
              </div>

              <div className="space-y-2">
                <Label>Trigger Condition</Label>
                <AlarmRuleBuilder value={condition} onChange={setCondition} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="alarm-notifiers">Notifiers (Optional)</Label>
                <select
                  id="alarm-notifiers"
                  multiple
                  value={notifierIds}
                  onChange={e => setNotifierIds(Array.from(e.target.selectedOptions, option => option.value))}
                  className="h-32 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm text-foreground focus-visible:outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  {notifiers?.items.map(notifier => (
                    <option key={notifier.id} value={notifier.id}>{notifier.name} ({notifier.type})</option>
                  ))}
                </select>
              </div>

              <Separator />

              <div>
                <h3 className="text-sm font-semibold mb-4 text-foreground">Advanced Settings</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="repeat-count">Required consecutive matches</Label>
                    <Input
                      id="repeat-count"
                      type="number"
                      min="1"
                      value={repeatCount}
                      onChange={e => setRepeatCount(parseInt(e.target.value))}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="for-duration">For duration (minutes)</Label>
                    <Input
                      id="for-duration"
                      type="number"
                      min="0"
                      value={forDurationMinutes}
                      onChange={e => setForDurationMinutes(parseInt(e.target.value))}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="cooldown">Cooldown (minutes)</Label>
                    <Input
                      id="cooldown"
                      type="number"
                      min="0"
                      value={cooldownMinutes}
                      onChange={e => setCooldownMinutes(parseInt(e.target.value))}
                    />
                  </div>

                  <div className="flex items-center gap-2 pt-6">
                    <input
                      type="checkbox"
                      id="notify_on_resolve"
                      checked={notifyOnResolve}
                      onChange={e => setNotifyOnResolve(e.target.checked)}
                      className="h-4 w-4 rounded border-input accent-primary"
                    />
                    <Label htmlFor="notify_on_resolve">Notify when resolved</Label>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate({ to: '/alarms' })}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending ? 'Saving...' : 'Create Alarm'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
