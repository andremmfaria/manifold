import { createRoute } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { providersApi, type Provider } from '@/api/providers'
import { connectionsApi } from '@/api/connections'
import {
  AuthCredentialFields,
  buildCredentials,
  EMPTY_CREDENTIALS,
  type AuthMode,
  type CredentialState,
} from '@/features/connections/AuthCredentialFields'

export const connectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/connections/connect',
  component: ConnectPage,
})

type SyncResult = {
  accounts: number
  transactions: number
  error?: string
  pending?: boolean
}

type FileFormState = {
  source: string
  authMode: AuthMode
  syncInterval: string
}

const SYNC_INTERVAL_OPTIONS = [
  { value: '15m', label: 'Every 15 minutes' },
  { value: '1h', label: 'Every hour' },
  { value: '6h', label: 'Every 6 hours' },
  { value: '1d', label: 'Daily' },
  { value: 'manual', label: 'Manual only' },
]

const AUTH_MODE_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'api_key', label: 'API Key' },
  { value: 'bearer', label: 'Bearer token' },
  { value: 'basic', label: 'Basic auth' },
]

function ConnectPage() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // JSON file provider dialog state
  const [fileDialogProvider, setFileDialogProvider] = useState<Provider | null>(null)
  const [fileForm, setFileForm] = useState<FileFormState>({
    source: '',
    authMode: 'none',
    syncInterval: '1h',
  })
  const [fileCredentials, setFileCredentials] = useState<CredentialState>(EMPTY_CREDENTIALS)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [createdConnectionId, setCreatedConnectionId] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const { data: providers = [], isLoading: providersLoading } = useQuery({
    queryKey: ['providers'],
    queryFn: providersApi.list,
  })

  const handleConnect = async (provider: Provider) => {
    if (provider.auth_kind === 'file') {
      // Open the JSON config dialog instead of redirecting
      setFileDialogProvider(provider)
      setFileForm({ source: '', authMode: 'none', syncInterval: '1h' })
      setFileCredentials(EMPTY_CREDENTIALS)
      setSyncResult(null)
      setCreatedConnectionId(null)
      setFormError(null)
      return
    }

    // OAuth flow: create then get auth url
    setIsLoading(true)
    setError(null)
    try {
      const connection = await connectionsApi.create({
        provider_type: provider.provider_type,
        display_name: provider.display_name,
      })
      const { auth_url } = await connectionsApi.getAuthUrl(connection.id)
      window.location.href = auth_url
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail ?? 'Failed to initiate connection')
      setIsLoading(false)
    }
  }

  const handleFileConnect = async () => {
    if (!fileDialogProvider) return
    if (!fileForm.source.trim()) {
      setFormError('File path or URL is required.')
      return
    }
    setIsLoading(true)
    setFormError(null)
    setSyncResult(null)

    try {
      const isUrl =
        fileForm.source.startsWith('http://') || fileForm.source.startsWith('https://')
      const config: Record<string, unknown> = {
        auth_mode: fileForm.authMode === 'none' ? undefined : fileForm.authMode,
        sync_interval: fileForm.syncInterval,
      }
      if (isUrl) {
        config.url = fileForm.source
      } else {
        config.path = fileForm.source
      }

      const credentials = buildCredentials(fileForm.authMode, fileCredentials)
      const connection = await connectionsApi.create({
        provider_type: fileDialogProvider.provider_type,
        display_name: fileDialogProvider.display_name,
        config,
        ...(credentials ? { credentials } : {}),
      })
      setCreatedConnectionId(connection.id)

      // Trigger sync then poll until terminal status or 30 s cap.
      try {
        await connectionsApi.sync(connection.id)
        const PENDING = new Set(['queued', 'running'])
        const MAX_ATTEMPTS = 15
        const INTERVAL_MS = 2_000
        let latest = null
        for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
          if (attempt > 0) {
            await new Promise((r) => setTimeout(r, INTERVAL_MS))
          }
          const runs = await connectionsApi.syncRuns(connection.id)
          latest = runs[0] ?? null
          if (!latest || !PENDING.has(latest.status)) break
          // Still in flight — update UI with pending indicator so user sees activity.
          setSyncResult({ accounts: 0, transactions: 0, error: undefined, pending: true })
        }
        if (latest?.status === 'failed') {
          setSyncResult({
            accounts: 0,
            transactions: 0,
            error: latest.error_code
              ? `${latest.error_code}${latest.error_detail ? ': ' + JSON.stringify(latest.error_detail) : ''}`
              : 'Sync failed',
          })
        } else {
          setSyncResult({
            accounts: latest?.accounts_synced ?? 0,
            transactions: latest?.transactions_synced ?? 0,
          })
        }
      } catch {
        setSyncResult({ accounts: 0, transactions: 0, error: 'Sync request failed' })
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setFormError(e.response?.data?.detail ?? 'Failed to create connection')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Connect a provider
          </h1>
          <p className="mt-1 text-muted-foreground">
            Select a financial institution to connect to Manifold.
          </p>
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
                    {provider.auth_kind === 'file'
                      ? 'Import from a JSON file or URL on a schedule.'
                      : 'Connect via secure OAuth.'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {provider.provider_type}
                  </span>
                </CardContent>
                <CardFooter>
                  <Button
                    onClick={() => void handleConnect(provider)}
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

        {isLoading && !fileDialogProvider && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="mt-4 font-medium text-foreground">Initiating connection...</p>
          </div>
        )}

        {/* JSON file provider config dialog */}
        <Dialog
          open={fileDialogProvider !== null}
          onOpenChange={(open) => {
            if (!open) setFileDialogProvider(null)
          }}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Configure JSON source</DialogTitle>
              <DialogDescription>
                Provide the file path or URL of your JSON data file and choose how often
                Manifold should read it.
              </DialogDescription>
            </DialogHeader>

            {syncResult ? (
              // Show load result after successful creation + sync
              <div className="space-y-4">
                {syncResult.pending ? (
                  <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-foreground space-y-1">
                    <p className="font-medium text-muted-foreground">Syncing&hellip;</p>
                    <p className="text-muted-foreground">Waiting for sync to complete.</p>
                  </div>
                ) : syncResult.error ? (
                  <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                    Sync failed: {syncResult.error}
                  </div>
                ) : (
                  <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-foreground space-y-1">
                    <p className="font-medium text-foreground">File loaded successfully.</p>
                    <p className="text-muted-foreground">
                      {syncResult.accounts} account{syncResult.accounts !== 1 ? 's' : ''},{' '}
                      {syncResult.transactions} transaction
                      {syncResult.transactions !== 1 ? 's' : ''} imported.
                    </p>
                  </div>
                )}
                {!syncResult.pending && (
                  <DialogFooter>
                    {createdConnectionId && (
                      <Button
                        onClick={() => {
                          setFileDialogProvider(null)
                          void navigate({ to: '/connections/$connectionId', params: { connectionId: createdConnectionId } })
                        }}
                      >
                        View connection
                      </Button>
                    )}
                    <Button variant="outline" onClick={() => setFileDialogProvider(null)}>
                      Done
                    </Button>
                  </DialogFooter>
                )}
              </div>
            ) : (
              // Config form
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="file-source">File path or URL</Label>
                  <Input
                    id="file-source"
                    placeholder="/data/finances.json or https://example.com/data.json"
                    value={fileForm.source}
                    onChange={(e) =>
                      setFileForm((f) => ({ ...f, source: e.target.value }))
                    }
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="auth-mode">Auth mode</Label>
                  <Select
                    value={fileForm.authMode}
                    onValueChange={(v) => {
                      setFileForm((f) => ({ ...f, authMode: v as AuthMode }))
                      setFileCredentials(EMPTY_CREDENTIALS)
                    }}
                  >
                    <SelectTrigger id="auth-mode" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {AUTH_MODE_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <AuthCredentialFields
                  authMode={fileForm.authMode}
                  credentials={fileCredentials}
                  onChange={(patch) => setFileCredentials((c) => ({ ...c, ...patch }))}
                  idPrefix="connect"
                />

                <div className="space-y-1.5">
                  <Label htmlFor="sync-interval">Sync frequency</Label>
                  <Select
                    value={fileForm.syncInterval}
                    onValueChange={(v) => setFileForm((f) => ({ ...f, syncInterval: v }))}
                  >
                    <SelectTrigger id="sync-interval" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SYNC_INTERVAL_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {formError && (
                  <p className="text-sm text-destructive">{formError}</p>
                )}

                <DialogFooter>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setFileDialogProvider(null)}
                    disabled={isLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void handleFileConnect()}
                    disabled={isLoading}
                  >
                    {isLoading ? 'Connecting…' : 'Connect & load'}
                  </Button>
                </DialogFooter>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
