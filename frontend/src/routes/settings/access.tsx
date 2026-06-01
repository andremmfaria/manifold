import { useState, useMemo } from 'react'
import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { client } from '@/api/client'
import type { ColumnDef } from '@tanstack/react-table'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardTitle } from '@/components/ui/card'
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

export const settingsAccessRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/access',
  beforeLoad: ({ context, location }: { context: { auth: AuthContextValue }; location: { href: string } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login', search: { redirect: location.href } })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: AccessPage,
})

// Mirrors AccessGrantResponse on the backend.
interface AccessGrant {
  id: string
  grantee_user_id: string
  grantee_username: string
  role: string
  granted_at: string
}

const ROLE_OPTIONS = ['viewer', 'editor'] as const

function GrantAccessDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<string>('viewer')

  const createGrant = useMutation({
    // Resolve the username to a user id (the list-users endpoint is superadmin-only),
    // then create the grant against that id.
    mutationFn: async ({ username, role }: { username: string; role: string }) => {
      const lookup = await client.get<{ id: string }>(
        `/api/v1/users/by-username/${encodeURIComponent(username)}`,
      )
      return client
        .post('/api/v1/users/me/access', { grantee_user_id: lookup.data.id, role })
        .then((res) => res.data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['access-grants'] })
      setUsername('')
      setRole('viewer')
      setOpen(false)
    },
  })

  const errorMessage = (() => {
    const err = createGrant.error
    if (!err) return null
    if (isAxiosError(err)) {
      const detail = err.response?.data?.error
      if (detail === 'self_grant_forbidden') return 'You cannot grant access to yourself.'
      if (err.response?.status === 404) return 'No active user found with that username.'
    }
    return 'Failed to grant access. Check the username and try again.'
  })()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) return
    createGrant.mutate({ username: username.trim(), role })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) createGrant.reset()
      }}
    >
      <DialogTrigger asChild>
        <Button>Grant access</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Grant access</DialogTitle>
          <DialogDescription>
            Give another user access to your accounts. Enter their user ID and the role to assign.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="grantee-username">Username</Label>
            <Input
              id="grantee-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. jdoe"
              autoComplete="off"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="grantee-role">Role</Label>
            <select
              id="grantee-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm capitalize shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt} value={opt} className="capitalize">
                  {opt}
                </option>
              ))}
            </select>
          </div>
          {errorMessage && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
              {errorMessage}
            </div>
          )}
          <DialogFooter>
            <Button type="submit" disabled={createGrant.isPending || !username.trim()}>
              {createGrant.isPending ? 'Granting…' : 'Grant access'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AccessPage() {
  const queryClient = useQueryClient()

  const {
    data: grants,
    isLoading,
    error,
  } = useQuery<AccessGrant[]>({
    queryKey: ['access-grants'],
    queryFn: () => client.get('/api/v1/users/me/access').then((res) => res.data),
  })

  const revokeGrant = useMutation({
    mutationFn: (grantId: string) => client.delete(`/api/v1/users/me/access/${grantId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['access-grants'] })
    },
  })

  const columns = useMemo<ColumnDef<AccessGrant, any>[]>(
    () => [
      {
        id: 'grantee',
        accessorKey: 'grantee_username',
        meta: { label: 'Grantee' },
        header: 'Grantee',
        cell: ({ row }) => (
          <span className="font-medium text-foreground">{row.original.grantee_username}</span>
        ),
      },
      {
        id: 'access_level',
        accessorKey: 'role',
        meta: { label: 'Access Level' },
        header: 'Access Level',
        cell: ({ row }) => (
          <Badge variant="secondary" className="capitalize">
            {row.original.role}
          </Badge>
        ),
      },
      {
        id: 'granted_at',
        accessorKey: 'granted_at',
        meta: { label: 'Granted At' },
        header: 'Granted At',
        cell: ({ row }) => (
          <span className="text-muted-foreground">
            {new Date(row.original.granted_at).toLocaleDateString()}
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
            <Button
              variant="destructive"
              size="sm"
              onClick={() => revokeGrant.mutate(row.original.id)}
              disabled={revokeGrant.isPending}
            >
              Revoke
            </Button>
          </div>
        ),
      },
    ],
    [revokeGrant],
  )

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Access Management
            </h2>
            <p className="mt-1 text-muted-foreground">Manage who has access to your data.</p>
          </div>
          <GrantAccessDialog />
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            Failed to load access grants
          </div>
        )}

        <Card>
          <CardContent className="p-4">
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : (
              <DataTable
                columns={columns}
                data={grants ?? []}
                emptyMessage="You haven't granted access to anyone."
                storageKey="access-grants"
                toolbar={<CardTitle>Active Grants</CardTitle>}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
