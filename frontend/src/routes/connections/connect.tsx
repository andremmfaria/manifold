import { createRoute, useNavigate } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { useState } from 'react'
import { client } from '@/api/client'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'

export const connectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/connections/connect',
  component: ConnectPage,
})

interface Provider {
  provider_type: string
  display_name: string
}

function ConnectPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: providers = [], isLoading: providersLoading } = useQuery({
    queryKey: ['providers'],
    queryFn: async () => {
      const r = await client.get<Provider[]>('/api/v1/providers')
      return r.data
    },
  })

  const handleConnect = async (provider: Provider) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await client.post<{ auth_url: string }>('/api/v1/connections', {
        provider_type: provider.provider_type,
        display_name: provider.display_name,
      })
      window.location.href = response.data.auth_url
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to initiate connection')
      setIsLoading(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Connect a provider</h1>
          <p className="mt-1 text-slate-600">Select a financial institution to connect to Manifold.</p>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {providersLoading ? (
          <div className="flex animate-pulse space-x-4">
            <div className="h-32 w-full rounded-xl bg-slate-200"></div>
            <div className="h-32 w-full rounded-xl bg-slate-200"></div>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {providers.map((provider) => (
              <button
                key={provider.provider_type}
                onClick={() => handleConnect(provider)}
                disabled={isLoading}
                className="flex flex-col items-start justify-between gap-4 rounded-xl border bg-white p-6 shadow-sm transition-colors hover:border-blue-500 hover:shadow-md disabled:opacity-50"
              >
                <div className="text-left">
                  <h3 className="text-lg font-semibold text-slate-900">{provider.display_name}</h3>
                  <p className="mt-1 text-sm text-slate-500">Connect to {provider.display_name} via secure OAuth flow.</p>
                </div>
                <div className="flex w-full items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wider text-slate-400">{provider.provider_type}</span>
                  <span className="text-sm font-medium text-blue-600">Connect &rarr;</span>
                </div>
              </button>
            ))}
            {providers.length === 0 && !providersLoading && (
              <p className="text-slate-500">No providers available.</p>
            )}
          </div>
        )}
        
        {isLoading && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/20 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
            <p className="mt-4 font-medium text-slate-900">Initiating connection...</p>
          </div>
        )}
      </div>
    </AppShell>
  )
}
