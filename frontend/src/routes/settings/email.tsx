import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  getEmailSettings,
  updateEmailSettings,
  testEmailSettings,
  listSuppressions,
  addSuppression,
  removeSuppression,
} from '@/api/email_settings'
import type { EmailSettingsUpdateRequest } from '@/types/email_settings'

export const settingsEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/email',
  beforeLoad: ({
    context,
    location,
  }: {
    context: { auth: AuthContextValue }
    location: { href: string }
  }) => {
    if (!context.auth.isAuthenticated)
      throw redirect({ to: '/login', search: { redirect: location.href } })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
    if (context.auth.role !== 'superadmin') throw redirect({ to: '/settings/access' })
  },
  component: EmailSettingsPage,
})

// ─── Secret field helpers ──────────────────────────────────────────────────────

const SECRET_PLACEHOLDER = 'Set (hidden) — leave blank to keep'

/** Returns true when a config value coming from the server is the masked sentinel. */
function isMasked(val: unknown): boolean {
  return val === '********'
}

/**
 * For a secret field: the value shown in state.
 * - masked sentinel  → '' (empty, placeholder shown via HTML placeholder attr)
 * - null / undefined → ''
 * - anything else    → the actual value
 */
function initSecret(val: unknown): string {
  if (val == null || isMasked(val)) return ''
  return String(val)
}

/** Plain string field initialiser. */
function initStr(val: unknown): string {
  if (val == null || isMasked(val)) return ''
  return String(val)
}

// ─── Provider config state ────────────────────────────────────────────────────

type Provider = 'smtp' | 'ses' | 'resend' | 'postmark' | 'mailgun' | 'brevo'

interface SmtpConfig {
  host: string
  port: string
  use_tls: boolean
  username: string
  password: string
}

interface SesConfig {
  region: string
  access_key_id: string
  secret_access_key: string
}

interface ResendConfig {
  api_key: string
  webhook_secret: string
}

interface PostmarkConfig {
  api_key: string
  webhook_token: string
}

interface MailgunConfig {
  api_key: string
  domain: string
  region: string
  webhook_signing_key: string
}

interface BrevoConfig {
  api_key: string
  webhook_secret: string
}

function emptySmtp(): SmtpConfig {
  return { host: '', port: '587', use_tls: true, username: '', password: '' }
}
function emptySes(): SesConfig {
  return { region: '', access_key_id: '', secret_access_key: '' }
}
function emptyResend(): ResendConfig {
  return { api_key: '', webhook_secret: '' }
}
function emptyPostmark(): PostmarkConfig {
  return { api_key: '', webhook_token: '' }
}
function emptyMailgun(): MailgunConfig {
  return { api_key: '', domain: '', region: 'us', webhook_signing_key: '' }
}
function emptyBrevo(): BrevoConfig {
  return { api_key: '', webhook_secret: '' }
}

type AnyProviderConfig =
  | SmtpConfig
  | SesConfig
  | ResendConfig
  | PostmarkConfig
  | MailgunConfig
  | BrevoConfig

/** Build the config dict to send to the API. Secret fields sent as '' mean "keep existing". */
function buildConfig(provider: Provider, cfg: AnyProviderConfig): Record<string, unknown> {
  switch (provider) {
    case 'smtp': {
      const c = cfg as SmtpConfig
      return {
        host: c.host,
        port: Number(c.port) || 587,
        use_tls: c.use_tls,
        username: c.username,
        password: c.password,
      }
    }
    case 'ses': {
      const c = cfg as SesConfig
      return {
        region: c.region,
        access_key_id: c.access_key_id,
        secret_access_key: c.secret_access_key,
      }
    }
    case 'resend': {
      const c = cfg as ResendConfig
      return { api_key: c.api_key, webhook_secret: c.webhook_secret }
    }
    case 'postmark': {
      const c = cfg as PostmarkConfig
      return { api_key: c.api_key, webhook_token: c.webhook_token }
    }
    case 'mailgun': {
      const c = cfg as MailgunConfig
      return {
        api_key: c.api_key,
        domain: c.domain,
        region: c.region,
        webhook_signing_key: c.webhook_signing_key,
      }
    }
    case 'brevo': {
      const c = cfg as BrevoConfig
      return { api_key: c.api_key, webhook_secret: c.webhook_secret }
    }
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function EmailSettingsPage() {
  const queryClient = useQueryClient()

  const { data: settings, isLoading } = useQuery({
    queryKey: ['email-settings'],
    queryFn: getEmailSettings,
  })

  // ── provider + config state ───────────────────────────────────────────────
  const [provider, setProvider] = useState<Provider>('smtp')
  const [smtpCfg, setSmtpCfg] = useState<SmtpConfig>(emptySmtp())
  const [sesCfg, setSesCfg] = useState<SesConfig>(emptySes())
  const [resendCfg, setResendCfg] = useState<ResendConfig>(emptyResend())
  const [postmarkCfg, setPostmarkCfg] = useState<PostmarkConfig>(emptyPostmark())
  const [mailgunCfg, setMailgunCfg] = useState<MailgunConfig>(emptyMailgun())
  const [brevoCfg, setBrevoCfg] = useState<BrevoConfig>(emptyBrevo())
  const [fromAddress, setFromAddress] = useState('')
  const [fromName, setFromName] = useState('')

  // ── populate from loaded data (run once after first successful fetch) ─────
  const [hydrated, setHydrated] = useState(false)
  if (settings && !hydrated) {
    const p = (settings.provider as Provider) || 'smtp'
    setProvider(p)
    setFromAddress(settings.from_address ?? '')
    setFromName(settings.from_name ?? '')
    const c = (settings.config ?? {}) as Record<string, unknown>
    if (p === 'smtp') {
      setSmtpCfg({
        host: initStr(c.host),
        port: initStr(c.port) || '587',
        use_tls: c.use_tls === true || c.use_tls === 'true',
        username: initStr(c.username),
        password: initSecret(c.password),
      })
    } else if (p === 'ses') {
      setSesCfg({
        region: initStr(c.region),
        access_key_id: initSecret(c.access_key_id),
        secret_access_key: initSecret(c.secret_access_key),
      })
    } else if (p === 'resend') {
      setResendCfg({ api_key: initSecret(c.api_key), webhook_secret: initSecret(c.webhook_secret) })
    } else if (p === 'postmark') {
      setPostmarkCfg({
        api_key: initSecret(c.api_key),
        webhook_token: initSecret(c.webhook_token),
      })
    } else if (p === 'mailgun') {
      setMailgunCfg({
        api_key: initSecret(c.api_key),
        domain: initStr(c.domain),
        region: initStr(c.region) || 'us',
        webhook_signing_key: initSecret(c.webhook_signing_key),
      })
    } else if (p === 'brevo') {
      setBrevoCfg({ api_key: initSecret(c.api_key), webhook_secret: initSecret(c.webhook_secret) })
    }
    setHydrated(true)
  }

  function handleProviderChange(val: string) {
    setProvider(val as Provider)
    // Reset all provider configs so prior provider's values don't bleed through
    setSmtpCfg(emptySmtp())
    setSesCfg(emptySes())
    setResendCfg(emptyResend())
    setPostmarkCfg(emptyPostmark())
    setMailgunCfg(emptyMailgun())
    setBrevoCfg(emptyBrevo())
  }

  // ── save mutation ─────────────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: (req: EmailSettingsUpdateRequest) => updateEmailSettings(req),
    onSuccess: () => {
      toast.success('Email settings saved')
      queryClient.invalidateQueries({ queryKey: ['email-settings'] })
      // allow re-hydration after save
      setHydrated(false)
    },
    onError: () => toast.error('Failed to save email settings'),
  })

  function handleSave(e: React.FormEvent) {
    e.preventDefault()
    const cfgMap: Record<Provider, AnyProviderConfig> = {
      smtp: smtpCfg,
      ses: sesCfg,
      resend: resendCfg,
      postmark: postmarkCfg,
      mailgun: mailgunCfg,
      brevo: brevoCfg,
    }
    saveMutation.mutate({
      provider,
      config: buildConfig(provider, cfgMap[provider]),
      from_address: fromAddress || null,
      from_name: fromName || null,
    })
  }

  // ── test email ────────────────────────────────────────────────────────────
  const [testAddress, setTestAddress] = useState('')
  const testMutation = useMutation({
    mutationFn: (addr: string) => testEmailSettings(addr),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success('Test email sent')
      } else {
        toast.error(result.error ?? 'Test failed')
      }
    },
    onError: () => toast.error('Test failed'),
  })

  // ── suppressions ─────────────────────────────────────────────────────────
  const { data: suppressions } = useQuery({
    queryKey: ['email-suppressions'],
    queryFn: () => listSuppressions(1),
  })

  const removeMutation = useMutation({
    mutationFn: (id: string) => removeSuppression(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['email-suppressions'] }),
    onError: () => toast.error('Failed to remove suppression'),
  })

  const [blockAddress, setBlockAddress] = useState('')
  const addMutation = useMutation({
    mutationFn: (addr: string) => addSuppression(addr, 'manual'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email-suppressions'] })
      setBlockAddress('')
    },
    onError: () => toast.error('Failed to add suppression'),
  })

  // ── render ────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <AppShell>
        <div className="p-6 max-w-2xl mx-auto">
          <p className="text-muted-foreground">Loading email settings…</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="p-6 max-w-2xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Email Settings</h2>
          <p className="mt-1 text-muted-foreground">
            Configure the outbound mail provider (Superadmin only).
          </p>
        </div>

        {/* ── Main settings form ─────────────────────────────────────────── */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle>Provider configuration</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleSave} className="space-y-6">
              {/* Provider select */}
              <div className="space-y-1.5">
                <Label htmlFor="provider">Provider</Label>
                <Select value={provider} onValueChange={handleProviderChange}>
                  <SelectTrigger id="provider" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="smtp">SMTP</SelectItem>
                    <SelectItem value="ses">Amazon SES</SelectItem>
                    <SelectItem value="resend">Resend</SelectItem>
                    <SelectItem value="postmark">Postmark</SelectItem>
                    <SelectItem value="mailgun">Mailgun</SelectItem>
                    <SelectItem value="brevo">Brevo</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* ── SMTP ─────────────────────────────────────────────────── */}
              {provider === 'smtp' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label htmlFor="smtp-host">Host</Label>
                      <Input
                        id="smtp-host"
                        value={smtpCfg.host}
                        onChange={(e) => setSmtpCfg((c) => ({ ...c, host: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="smtp-port">Port</Label>
                      <Input
                        id="smtp-port"
                        type="number"
                        value={smtpCfg.port}
                        onChange={(e) => setSmtpCfg((c) => ({ ...c, port: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="smtp-username">Username</Label>
                      <Input
                        id="smtp-username"
                        value={smtpCfg.username}
                        onChange={(e) => setSmtpCfg((c) => ({ ...c, username: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="smtp-password">
                        Password
                        <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                          Leave blank to keep existing value.
                        </span>
                      </Label>
                      <Input
                        id="smtp-password"
                        type="password"
                        placeholder={
                          settings?.config?.password === '********' ? SECRET_PLACEHOLDER : undefined
                        }
                        value={smtpCfg.password}
                        onChange={(e) => setSmtpCfg((c) => ({ ...c, password: e.target.value }))}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="smtp-use-tls"
                      checked={smtpCfg.use_tls}
                      onChange={(e) => setSmtpCfg((c) => ({ ...c, use_tls: e.target.checked }))}
                      className="h-4 w-4 rounded border-input accent-primary"
                    />
                    <Label htmlFor="smtp-use-tls" className="font-normal cursor-pointer">
                      Use TLS
                    </Label>
                  </div>
                </div>
              )}

              {/* ── SES ──────────────────────────────────────────────────── */}
              {provider === 'ses' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="ses-region">Region</Label>
                    <Input
                      id="ses-region"
                      value={sesCfg.region}
                      onChange={(e) => setSesCfg((c) => ({ ...c, region: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="ses-access-key-id">
                      Access Key ID
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="ses-access-key-id"
                      placeholder={
                        settings?.config?.access_key_id === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={sesCfg.access_key_id}
                      onChange={(e) => setSesCfg((c) => ({ ...c, access_key_id: e.target.value }))}
                    />
                  </div>
                  <div className="col-span-2 space-y-1.5">
                    <Label htmlFor="ses-secret-access-key">
                      Secret Access Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="ses-secret-access-key"
                      type="password"
                      placeholder={
                        settings?.config?.secret_access_key === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={sesCfg.secret_access_key}
                      onChange={(e) =>
                        setSesCfg((c) => ({ ...c, secret_access_key: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}

              {/* ── Resend ───────────────────────────────────────────────── */}
              {provider === 'resend' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="resend-api-key">
                      API Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        Leave blank to keep existing value.
                      </span>
                    </Label>
                    <Input
                      id="resend-api-key"
                      type="password"
                      placeholder={
                        settings?.config?.api_key === '********' ? SECRET_PLACEHOLDER : undefined
                      }
                      value={resendCfg.api_key}
                      onChange={(e) => setResendCfg((c) => ({ ...c, api_key: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="resend-webhook-secret">
                      Webhook Secret
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="resend-webhook-secret"
                      type="password"
                      placeholder={
                        settings?.config?.webhook_secret === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={resendCfg.webhook_secret}
                      onChange={(e) =>
                        setResendCfg((c) => ({ ...c, webhook_secret: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}

              {/* ── Postmark ─────────────────────────────────────────────── */}
              {provider === 'postmark' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="postmark-api-key">
                      API Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        Leave blank to keep existing value.
                      </span>
                    </Label>
                    <Input
                      id="postmark-api-key"
                      type="password"
                      placeholder={
                        settings?.config?.api_key === '********' ? SECRET_PLACEHOLDER : undefined
                      }
                      value={postmarkCfg.api_key}
                      onChange={(e) => setPostmarkCfg((c) => ({ ...c, api_key: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="postmark-webhook-token">
                      Webhook Token
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="postmark-webhook-token"
                      type="password"
                      placeholder={
                        settings?.config?.webhook_token === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={postmarkCfg.webhook_token}
                      onChange={(e) =>
                        setPostmarkCfg((c) => ({ ...c, webhook_token: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}

              {/* ── Mailgun ──────────────────────────────────────────────── */}
              {provider === 'mailgun' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="mailgun-api-key">
                      API Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        Leave blank to keep existing value.
                      </span>
                    </Label>
                    <Input
                      id="mailgun-api-key"
                      type="password"
                      placeholder={
                        settings?.config?.api_key === '********' ? SECRET_PLACEHOLDER : undefined
                      }
                      value={mailgunCfg.api_key}
                      onChange={(e) => setMailgunCfg((c) => ({ ...c, api_key: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="mailgun-domain">Domain</Label>
                    <Input
                      id="mailgun-domain"
                      value={mailgunCfg.domain}
                      onChange={(e) => setMailgunCfg((c) => ({ ...c, domain: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="mailgun-region">Region</Label>
                    <Select
                      value={mailgunCfg.region}
                      onValueChange={(v) => setMailgunCfg((c) => ({ ...c, region: v }))}
                    >
                      <SelectTrigger id="mailgun-region" className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="us">US</SelectItem>
                        <SelectItem value="eu">EU</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="mailgun-webhook-signing-key">
                      Webhook Signing Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="mailgun-webhook-signing-key"
                      type="password"
                      placeholder={
                        settings?.config?.webhook_signing_key === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={mailgunCfg.webhook_signing_key}
                      onChange={(e) =>
                        setMailgunCfg((c) => ({ ...c, webhook_signing_key: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}

              {/* ── Brevo ────────────────────────────────────────────────── */}
              {provider === 'brevo' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="brevo-api-key">
                      API Key
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        Leave blank to keep existing value.
                      </span>
                    </Label>
                    <Input
                      id="brevo-api-key"
                      type="password"
                      placeholder={
                        settings?.config?.api_key === '********' ? SECRET_PLACEHOLDER : undefined
                      }
                      value={brevoCfg.api_key}
                      onChange={(e) => setBrevoCfg((c) => ({ ...c, api_key: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="brevo-webhook-secret">
                      Webhook Secret
                      <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                        optional — leave blank to keep
                      </span>
                    </Label>
                    <Input
                      id="brevo-webhook-secret"
                      type="password"
                      placeholder={
                        settings?.config?.webhook_secret === '********'
                          ? SECRET_PLACEHOLDER
                          : undefined
                      }
                      value={brevoCfg.webhook_secret}
                      onChange={(e) =>
                        setBrevoCfg((c) => ({ ...c, webhook_secret: e.target.value }))
                      }
                    />
                  </div>
                </div>
              )}

              {/* ── Common: from_address / from_name ─────────────────────── */}
              <div className="grid grid-cols-2 gap-4 border-t pt-4">
                <div className="space-y-1.5">
                  <Label htmlFor="from-address">From address</Label>
                  <Input
                    id="from-address"
                    type="email"
                    value={fromAddress}
                    onChange={(e) => setFromAddress(e.target.value)}
                    placeholder="noreply@example.com"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="from-name">
                    From name
                    <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                      optional
                    </span>
                  </Label>
                  <Input
                    id="from-name"
                    value={fromName}
                    onChange={(e) => setFromName(e.target.value)}
                    placeholder="Manifold"
                  />
                </div>
              </div>

              <div className="pt-2">
                <Button type="submit" disabled={saveMutation.isPending}>
                  {saveMutation.isPending ? 'Saving…' : 'Save settings'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* ── Test email ─────────────────────────────────────────────────── */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle>Send test email</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="test-address">Recipient address</Label>
                <Input
                  id="test-address"
                  type="email"
                  value={testAddress}
                  onChange={(e) => setTestAddress(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                disabled={!testAddress || testMutation.isPending}
                onClick={() => testMutation.mutate(testAddress)}
              >
                {testMutation.isPending ? 'Sending…' : 'Send test email'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* ── Suppression list ──────────────────────────────────────────── */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle>Suppression list</CardTitle>
          </CardHeader>
          <CardContent className="pt-6 space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Address (HMAC)</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {(suppressions?.items ?? []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground text-sm">
                      No suppressed addresses.
                    </TableCell>
                  </TableRow>
                ) : (
                  suppressions?.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">
                        {item.address_hmac.slice(0, 16)}…
                      </TableCell>
                      <TableCell className="text-sm">{item.reason}</TableCell>
                      <TableCell className="text-sm">{item.source}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={removeMutation.isPending}
                          onClick={() => removeMutation.mutate(item.id)}
                        >
                          Unblock
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>

            {/* Manual block row */}
            <div className="flex items-end gap-3 border-t pt-4">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="block-address">Block address manually</Label>
                <Input
                  id="block-address"
                  type="email"
                  value={blockAddress}
                  onChange={(e) => setBlockAddress(e.target.value)}
                  placeholder="user@example.com"
                />
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={!blockAddress || addMutation.isPending}
                onClick={() => addMutation.mutate(blockAddress)}
              >
                {addMutation.isPending ? 'Blocking…' : 'Block'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
