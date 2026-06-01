import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export type AuthMode = 'none' | 'api_key' | 'bearer' | 'basic'

export type CredentialState = {
  api_key: string
  access_token: string
  username: string
  password: string
}

export const EMPTY_CREDENTIALS: CredentialState = {
  api_key: '',
  access_token: '',
  username: '',
  password: '',
}

/**
 * Builds the credentials object to send for a given auth mode.
 * Returns undefined when all relevant fields are blank (preserves existing secrets on edit).
 */
export function buildCredentials(
  mode: AuthMode,
  creds: CredentialState,
): Record<string, string> | undefined {
  if (mode === 'api_key') {
    return creds.api_key ? { api_key: creds.api_key } : undefined
  }
  if (mode === 'bearer') {
    return creds.access_token ? { access_token: creds.access_token } : undefined
  }
  if (mode === 'basic') {
    return creds.username || creds.password
      ? { username: creds.username, password: creds.password }
      : undefined
  }
  return undefined
}

type Props = {
  authMode: AuthMode
  credentials: CredentialState
  onChange: (patch: Partial<CredentialState>) => void
  /** When true, inputs show a "leave blank to keep" hint (edit flow). */
  isEdit?: boolean
  idPrefix?: string
}

export function AuthCredentialFields({
  authMode,
  credentials,
  onChange,
  isEdit = false,
  idPrefix = 'cred',
}: Props) {
  if (authMode === 'none') return null

  const hint = isEdit ? (
    <p className="text-xs text-muted-foreground">Leave blank to keep the current credentials.</p>
  ) : null

  if (authMode === 'api_key') {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-api-key`}>API key</Label>
        <Input
          id={`${idPrefix}-api-key`}
          type="password"
          autoComplete="new-password"
          placeholder={isEdit ? '••••••••' : 'Enter API key'}
          value={credentials.api_key}
          onChange={(e) => onChange({ api_key: e.target.value })}
        />
        {hint}
      </div>
    )
  }

  if (authMode === 'bearer') {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-access-token`}>Access token</Label>
        <Input
          id={`${idPrefix}-access-token`}
          type="password"
          autoComplete="new-password"
          placeholder={isEdit ? '••••••••' : 'Enter access token'}
          value={credentials.access_token}
          onChange={(e) => onChange({ access_token: e.target.value })}
        />
        {hint}
      </div>
    )
  }

  if (authMode === 'basic') {
    return (
      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-username`}>Username</Label>
          <Input
            id={`${idPrefix}-username`}
            type="text"
            autoComplete="new-password"
            placeholder={isEdit ? 'Current username' : 'Enter username'}
            value={credentials.username}
            onChange={(e) => onChange({ username: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idPrefix}-password`}>Password</Label>
          <Input
            id={`${idPrefix}-password`}
            type="password"
            autoComplete="new-password"
            placeholder={isEdit ? '••••••••' : 'Enter password'}
            value={credentials.password}
            onChange={(e) => onChange({ password: e.target.value })}
          />
        </div>
        {hint}
      </div>
    )
  }

  return null
}
