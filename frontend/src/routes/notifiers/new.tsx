import { useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useCreateNotifier } from '@/features/notifiers/useNotifiers'
import { rootRoute } from '../__root'

export const notifiersNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/notifiers/new',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
  },
  component: NewNotifierPage,
})

function NewNotifierPage() {
  const navigate = useNavigate()
  const { mutateAsync: createNotifier, isPending } = useCreateNotifier()

  const [name, setName] = useState('')
  const [type, setType] = useState('email')
  const [config, setConfig] = useState('{\n  "smtp_host": "smtp.example.com",\n  "smtp_port": 587,\n  "from_address": "alarms@example.com",\n  "to_address": "you@example.com"\n}')
  const [error, setError] = useState('')

  const handleTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value;
    setType(newType);
    
    // Provide sensible default config based on type
    if (newType === 'email') {
      setConfig('{\n  "smtp_host": "smtp.example.com",\n  "smtp_port": 587,\n  "from_address": "alarms@example.com",\n  "to_address": "you@example.com"\n}');
    } else if (newType === 'webhook') {
      setConfig('{\n  "url": "https://example.com/webhook",\n  "method": "POST",\n  "headers": {}\n}');
    } else if (newType === 'slack') {
      setConfig('{\n  "webhook_url": "https://hooks.slack.com/services/...",\n  "channel": "#alerts"\n}');
    } else if (newType === 'telegram') {
      setConfig('{\n  "bot_token": "YOUR_BOT_TOKEN",\n  "chat_id": "YOUR_CHAT_ID"\n}');
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    try {
      if (!name) throw new Error("Name is required");
      
      let parsedConfig;
      try {
        parsedConfig = JSON.parse(config);
      } catch (e) {
        throw new Error("Invalid JSON in configuration");
      }

      await createNotifier({
        name,
        type,
        config: parsedConfig,
        is_enabled: true
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
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Add Notifier</h1>
          <p className="mt-1 text-slate-500">Configure a new destination for alarm notifications.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 bg-white p-6 rounded-xl border shadow-sm">
          {error && <div className="p-3 bg-red-50 text-red-700 text-sm rounded-md">{error}</div>}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Notifier Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border"
              placeholder="e.g. Work Email, On-Call Slack"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
            <select
              value={type}
              onChange={handleTypeChange}
              className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border bg-white"
            >
              <option value="email">Email</option>
              <option value="webhook">Webhook</option>
              <option value="slack">Slack</option>
              <option value="telegram">Telegram</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Configuration (JSON)</label>
            <textarea
              required
              value={config}
              onChange={e => setConfig(e.target.value)}
              className="w-full rounded-md border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2 border font-mono text-sm h-48"
              placeholder="{}"
            />
            <p className="text-xs text-slate-500 mt-1">Provide the connection details in JSON format.</p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <button
              type="button"
              onClick={() => navigate({ to: '/notifiers' })}
              className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 disabled:opacity-50"
            >
              {isPending ? 'Saving...' : 'Add Notifier'}
            </button>
          </div>
        </form>
      </div>
    </AppShell>
  )
}
