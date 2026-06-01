import { useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useCreateNotifier } from '@/features/notifiers/useNotifiers'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { rootRoute } from '../__root'

export const notifiersNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/notifiers/new',
  beforeLoad: ({
    context,
    location,
  }: {
    context: { auth: AuthContextValue }
    location: { href: string }
  }) => {
    if (!context.auth.isAuthenticated)
      throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: NewNotifierPage,
})

function NewNotifierPage() {
  const navigate = useNavigate()
  const { mutateAsync: createNotifier, isPending } = useCreateNotifier()

  const [name, setName] = useState('')
  const [type, setType] = useState('email')
  const [config, setConfig] = useState('{\n  "to_address": "you@example.com"\n}')
  const [error, setError] = useState('')

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value
    setType(newType)

    // Provide sensible default config based on type
    if (newType === 'email') {
      setConfig('{\n  "to_address": "you@example.com"\n}')
    } else if (newType === 'webhook') {
      setConfig(
        '{\n  "url": "https://example.com/webhook",\n  "method": "POST",\n  "headers": {}\n}',
      )
    } else if (newType === 'slack') {
      setConfig(
        '{\n  "webhook_url": "https://hooks.slack.com/services/...",\n  "channel": "#alerts"\n}',
      )
    } else if (newType === 'telegram') {
      setConfig('{\n  "bot_token": "YOUR_BOT_TOKEN",\n  "chat_id": "YOUR_CHAT_ID"\n}')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    try {
      if (!name) throw new Error('Name is required')

      let parsedConfig
      try {
        parsedConfig = JSON.parse(config)
      } catch (e) {
        throw new Error('Invalid JSON in configuration')
      }

      await createNotifier({
        name,
        type,
        config: parsedConfig,
        is_enabled: true,
      })
      navigate({ to: '/notifiers' })
    } catch (err: any) {
      setError(err.message || 'Failed to create notifier')
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-2xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Add Notifier</h1>
          <p className="mt-1 text-muted-foreground">
            Configure a new destination for alarm notifications.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Notifier Details</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-lg border border-destructive/20">
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="notifier-name">Notifier Name</Label>
                <Input
                  id="notifier-name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Work Email, On-Call Slack"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="notifier-type">Type</Label>
                <select
                  id="notifier-type"
                  value={type}
                  onChange={handleTypeChange}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm text-foreground focus-visible:outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <option value="email">Email</option>
                  <option value="webhook">Webhook</option>
                  <option value="slack">Slack</option>
                  <option value="telegram">Telegram</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="notifier-config">Configuration (JSON)</Label>
                <textarea
                  id="notifier-config"
                  required
                  value={config}
                  onChange={(e) => setConfig(e.target.value)}
                  className="h-48 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 font-mono text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  placeholder="{}"
                />
                <p className="text-xs text-muted-foreground">
                  Provide the connection details in JSON format.
                </p>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate({ to: '/notifiers' })}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending ? 'Saving...' : 'Add Notifier'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
