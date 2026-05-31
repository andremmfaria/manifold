import { createRoute } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { useState } from 'react'
import { client } from '@/api/client'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

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
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Connect a provider</h1>
          <p className="mt-1 text-muted-foreground">Select a financial institution to connect to Manifold.</p>
        </div>

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {providersLoading ? (
          <div className="grid gap-4 lg:grid-cols-3">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {providers.map((provider) => (
              <Card
                key={provider.provider_type}
                className="transition-all hover:ring-2 hover:ring-primary/40"
              >
                <CardHeader>
                  <CardTitle>{provider.display_name}</CardTitle>
                  <CardDescription>
                    Connect to {provider.display_name} via secure OAuth flow.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {provider.provider_type}
                  </span>
                </CardContent>
                <CardFooter>
                  <Button
                    onClick={() => handleConnect(provider)}
                    disabled={isLoading}
                    className="w-full"
                  >
                    Connect &rarr;
                  </Button>
                </CardFooter>
              </Card>
            ))}
            {providers.length === 0 && !providersLoading && (
              <p className="text-muted-foreground">No providers available.</p>
            )}
          </div>
        )}

        {isLoading && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="mt-4 font-medium text-foreground">Initiating connection...</p>
          </div>
        )}
      </div>
    </AppShell>
  )
}
