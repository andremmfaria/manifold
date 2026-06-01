import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useMemo, useRef } from 'react'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import type { ColumnDef } from '@tanstack/react-table'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { DataTable } from '@/components/ui/data-table'
import { usersApi } from '@/api/users'
import type { CreateUserRequest } from '@/api/users'

export const settingsUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/users',
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
  component: UsersPage,
})

interface User {
  id: string
  username: string
  email: string | null
  first_name: string | null
  last_name: string | null
  role: string
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

const ROLE_OPTIONS = ['user', 'admin', 'superadmin'] as const

// ─── Bulk import ─────────────────────────────────────────────────────────────

interface BulkRow {
  username: string
  password: string
  role: string
  email?: string | null
  first_name?: string | null
  last_name?: string | null
  must_change_password?: boolean
}

interface BulkFailure {
  index: number
  username: string
  message: string
}

const BULK_TEMPLATE: BulkRow[] = [
  {
    username: 'alice',
    password: 'changeme123',
    role: 'user',
    email: 'alice@example.com',
    first_name: 'Alice',
    last_name: 'Smith',
    must_change_password: true,
  },
]

const TEMPLATE_BLOB = new Blob([JSON.stringify(BULK_TEMPLATE, null, 2)], {
  type: 'application/json',
})

function downloadTemplate() {
  const url = URL.createObjectURL(TEMPLATE_BLOB)
  const a = document.createElement('a')
  a.href = url
  a.download = 'users-template.json'
  a.click()
  URL.revokeObjectURL(url)
}

function validateBulkRows(rows: unknown[]): { valid: BulkRow[]; errors: string[] } {
  const errors: string[] = []
  const valid: BulkRow[] = []

  rows.forEach((row, i) => {
    if (typeof row !== 'object' || row === null) {
      errors.push(`Row ${i + 1}: not an object`)
      return
    }
    const r = row as Record<string, unknown>
    const missing: string[] = []
    if (!r.username || typeof r.username !== 'string') missing.push('username')
    if (!r.password || typeof r.password !== 'string') missing.push('password')
    if (!r.role || typeof r.role !== 'string') missing.push('role')
    if (missing.length > 0) {
      errors.push(`Row ${i + 1}: missing required fields: ${missing.join(', ')}`)
      return
    }
    if (!(ROLE_OPTIONS as readonly string[]).includes(r.role as string)) {
      errors.push(
        `Row ${i + 1}: invalid role "${r.role}" — must be one of ${ROLE_OPTIONS.join(', ')}`,
      )
      return
    }
    valid.push({
      username: r.username as string,
      password: r.password as string,
      role: r.role as string,
      email: (r.email as string | null | undefined) ?? null,
      first_name: (r.first_name as string | null | undefined) ?? null,
      last_name: (r.last_name as string | null | undefined) ?? null,
      must_change_password:
        typeof r.must_change_password === 'boolean' ? r.must_change_password : false,
    })
  })

  return { valid, errors }
}

interface BulkImportResult {
  total: number
  succeeded: number
  failures: BulkFailure[]
}

function BulkImportDialog({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false)
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [rows, setRows] = useState<BulkRow[]>([])
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<BulkImportResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function reset() {
    setParseErrors([])
    setRows([])
    setResult(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset()
    setOpen(next)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setParseErrors([])
    setRows([])
    setResult(null)

    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target?.result as string)
        if (!Array.isArray(parsed)) {
          setParseErrors(['File must contain a JSON array of user objects.'])
          return
        }
        const { valid, errors } = validateBulkRows(parsed)
        if (errors.length > 0) {
          setParseErrors(errors)
          return
        }
        setRows(valid)
      } catch {
        setParseErrors(['Invalid JSON — could not parse file.'])
      }
    }
    reader.readAsText(file)
  }

  async function handleImport() {
    if (rows.length === 0) return
    setImporting(true)
    try {
      const results = await Promise.allSettled(
        rows.map((row) => usersApi.create(row as CreateUserRequest)),
      )
      const failures: BulkFailure[] = []
      results.forEach((r, i) => {
        if (r.status === 'rejected') {
          const err = r.reason
          let message = 'Unknown error'
          if (isAxiosError(err)) {
            if (err.response?.status === 409) {
              message = 'Username already exists'
            } else if (err.response?.data?.detail) {
              message = String(err.response.data.detail)
            } else {
              message = `HTTP ${err.response?.status ?? 'error'}`
            }
          }
          failures.push({ index: i + 1, username: rows[i].username, message })
        }
      })
      const succeeded = results.length - failures.length
      setResult({ total: rows.length, succeeded, failures })
      onImported()
      if (failures.length === 0) {
        toast.success(`Imported ${succeeded} user${succeeded !== 1 ? 's' : ''}`)
      } else {
        toast.warning(`Imported ${succeeded} of ${rows.length} users (${failures.length} failed)`)
      }
    } finally {
      setImporting(false)
    }
  }

  const canImport = rows.length > 0 && parseErrors.length === 0 && !result

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">Bulk add (JSON)</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Bulk add users</DialogTitle>
          <DialogDescription>
            Upload a JSON file containing an array of user objects. Each item must have{' '}
            <code className="text-xs font-mono">username</code>,{' '}
            <code className="text-xs font-mono">password</code>, and{' '}
            <code className="text-xs font-mono">role</code> (one of{' '}
            <code className="text-xs font-mono">{ROLE_OPTIONS.join(' | ')}</code>). Optional:{' '}
            <code className="text-xs font-mono">email</code>,{' '}
            <code className="text-xs font-mono">first_name</code>,{' '}
            <code className="text-xs font-mono">last_name</code>,{' '}
            <code className="text-xs font-mono">must_change_password</code>.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="bulk-file" className="shrink-0">
              JSON file
            </Label>
            <Button type="button" variant="outline" size="sm" onClick={downloadTemplate}>
              Download template
            </Button>
          </div>
          <input
            ref={fileInputRef}
            id="bulk-file"
            type="file"
            accept=".json,application/json"
            onChange={handleFileChange}
            className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-muted file:px-3 file:py-1 file:text-xs file:font-medium file:text-foreground hover:file:bg-muted/80 cursor-pointer"
          />

          {parseErrors.length > 0 && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive space-y-1">
              {parseErrors.map((e, i) => (
                <p key={i}>{e}</p>
              ))}
            </div>
          )}

          {rows.length > 0 && !result && (
            <p className="text-sm text-muted-foreground">
              {rows.length} user{rows.length !== 1 ? 's' : ''} ready to import.
            </p>
          )}

          {result && (
            <div className="rounded-lg border border-border p-3 space-y-2 text-sm">
              <p className="font-medium">
                Import complete: {result.succeeded} / {result.total} succeeded.
              </p>
              {result.failures.length > 0 && (
                <div className="space-y-1">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    Failures
                  </p>
                  {result.failures.map((f) => (
                    <p key={f.index} className="text-destructive">
                      Row {f.index} ({f.username}): {f.message}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {result ? 'Close' : 'Cancel'}
          </Button>
          {!result && (
            <Button onClick={handleImport} disabled={!canImport || importing}>
              {importing
                ? 'Importing...'
                : `Import${rows.length > 0 ? ` ${rows.length} users` : ''}`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function UsersPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [role, setRole] = useState('user')
  const [mustChangePassword, setMustChangePassword] = useState(true)

  const {
    data: users,
    isLoading,
    error,
  } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => usersApi.list(),
  })

  const createUser = useMutation({
    mutationFn: () =>
      usersApi.create({
        username,
        password,
        role,
        email: email || null,
        first_name: firstName || null,
        last_name: lastName || null,
        must_change_password: mustChangePassword,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setUsername('')
      setPassword('')
      setEmail('')
      setFirstName('')
      setLastName('')
      setRole('user')
      setMustChangePassword(true)
    },
  })

  const deactivateUser = useMutation({
    mutationFn: (id: string) => usersApi.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  const columns = useMemo<ColumnDef<User, any>[]>(
    () => [
      {
        id: 'username',
        accessorKey: 'username',
        meta: { label: 'Username' },
        header: 'Username',
        cell: ({ row }) => (
          <span className="font-medium text-foreground">{row.original.username}</span>
        ),
      },
      {
        id: 'role',
        accessorKey: 'role',
        meta: { label: 'Role' },
        header: 'Role',
        cell: ({ row }) => (
          <Badge variant="secondary" className="capitalize">
            {row.original.role}
          </Badge>
        ),
      },
      {
        id: 'status',
        accessorKey: 'is_active',
        meta: { label: 'Status' },
        header: 'Status',
        cell: ({ row }) => (
          <Badge variant={row.original.is_active ? 'default' : 'outline'}>
            {row.original.is_active ? 'Active' : 'Inactive'}
          </Badge>
        ),
      },
      {
        id: 'created',
        accessorKey: 'created_at',
        meta: { label: 'Created' },
        header: 'Created',
        cell: ({ row }) => (
          <span className="text-muted-foreground text-xs">
            {new Date(row.original.created_at).toLocaleDateString()}
          </span>
        ),
      },
      {
        id: 'actions',
        meta: { label: 'Actions' },
        header: () => <div className="text-right">Actions</div>,
        enableHiding: false,
        enableResizing: false,
        cell: ({ row }) => (
          <div className="text-right">
            {row.original.is_active && (
              <Button
                variant="destructive"
                size="xs"
                onClick={() => deactivateUser.mutate(row.original.id)}
                disabled={deactivateUser.isPending}
              >
                Deactivate
              </Button>
            )}
          </div>
        ),
      },
    ],
    [deactivateUser],
  )

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Users</h2>
          <p className="mt-1 text-muted-foreground">Manage system users (Superadmin only).</p>
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            Failed to load users
          </div>
        )}

        <Card>
          {/* The "User List" title is rendered in the DataTable's left toolbar slot so it
              shares one row with the Preferences button (same justify-between flex row),
              instead of sitting alone in a CardHeader above a detached Preferences row. */}
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                <CardTitle>User List</CardTitle>
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <DataTable
                toolbar={<CardTitle>User List</CardTitle>}
                columns={columns}
                data={users ?? []}
                emptyMessage="No users found."
                storageKey="users"
                onRowClick={(u) =>
                  void navigate({
                    to: '/settings/users/$userId',
                    params: { userId: u.id },
                  })
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <div className="flex items-center justify-between">
              <CardTitle>Create User</CardTitle>
              <BulkImportDialog
                onImported={() => queryClient.invalidateQueries({ queryKey: ['users'] })}
              />
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                createUser.mutate()
              }}
              className="space-y-4"
            >
              {createUser.isError && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                  Failed to create user
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="first-name">First name</Label>
                  <Input
                    id="first-name"
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="last-name">Last name</Label>
                  <Input
                    id="last-name"
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="role">Role</Label>
                  <Select value={role} onValueChange={setRole}>
                    <SelectTrigger id="role" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">User</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="superadmin">Superadmin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="must-change-password"
                  checked={mustChangePassword}
                  onChange={(e) => setMustChangePassword(e.target.checked)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <Label htmlFor="must-change-password" className="font-normal cursor-pointer">
                  Must change password on first login
                </Label>
              </div>

              <div className="pt-2">
                <Button type="submit" disabled={createUser.isPending}>
                  {createUser.isPending ? 'Creating...' : 'Create User'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
