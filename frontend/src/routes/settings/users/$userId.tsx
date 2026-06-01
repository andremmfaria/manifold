import { createRoute, redirect, useNavigate, useParams } from '@tanstack/react-router'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { isAxiosError } from 'axios'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { usersApi } from '@/api/users'
import type { UpdateUserRequest } from '@/api/users'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { rootRoute } from '../../__root'

export const settingsUserDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/users/$userId',
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
  component: UserDetailPage,
})

const ROLE_OPTIONS = ['user', 'admin', 'superadmin'] as const

function UserDetailPage() {
  const { userId } = useParams({ from: '/settings/users/$userId' })
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['users', userId],
    queryFn: () => usersApi.get(userId),
  })

  // Edit form state — seeded from fetched user when it arrives.
  const [editOpen, setEditOpen] = useState(false)
  const [editRole, setEditRole] = useState('')
  const [editFirstName, setEditFirstName] = useState('')
  const [editLastName, setEditLastName] = useState('')
  const [editIsActive, setEditIsActive] = useState(true)
  const [editMustChangePassword, setEditMustChangePassword] = useState(false)

  const [deleteOpen, setDeleteOpen] = useState(false)

  function openEdit() {
    if (!user) return
    setEditRole(user.role)
    setEditFirstName(user.first_name ?? '')
    setEditLastName(user.last_name ?? '')
    setEditIsActive(user.is_active)
    setEditMustChangePassword(user.must_change_password)
    setEditOpen(true)
  }

  const updateUser = useMutation({
    mutationFn: (data: UpdateUserRequest) => usersApi.update(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users', userId] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User updated')
      setEditOpen(false)
    },
    onError: (err) => {
      const msg =
        isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : 'Failed to update user'
      toast.error(msg)
    },
  })

  const deleteUser = useMutation({
    mutationFn: () => usersApi.remove(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User deleted')
      void navigate({ to: '/settings/users' })
    },
    onError: (err) => {
      const msg =
        isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : 'Failed to delete user'
      toast.error(msg)
      setDeleteOpen(false)
    },
  })

  function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault()
    updateUser.mutate({
      role: editRole,
      first_name: editFirstName || null,
      last_name: editLastName || null,
      is_active: editIsActive,
      must_change_password: editMustChangePassword,
    })
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6 p-6 max-w-3xl mx-auto">
          <Skeleton className="h-24 rounded-xl" />
          <Skeleton className="h-48 rounded-xl" />
        </div>
      </AppShell>
    )
  }

  if (error || !user) {
    return (
      <AppShell>
        <div className="p-6 max-w-3xl mx-auto">
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            {error ? 'Failed to load user' : 'User not found'}
          </div>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => void navigate({ to: '/settings/users' })}
          >
            Back to Users
          </Button>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-3xl mx-auto">
        {/* Header card */}
        <Card>
          <CardContent className="flex items-center justify-between py-6">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  {user.username}
                </h1>
                <Badge variant="secondary" className="capitalize">
                  {user.role}
                </Badge>
                <Badge variant={user.is_active ? 'default' : 'outline'}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground font-mono">{user.id}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="outline" onClick={() => void navigate({ to: '/settings/users' })}>
                Back
              </Button>
              <Button variant="outline" onClick={openEdit}>
                Edit
              </Button>
              <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                <DialogTrigger asChild>
                  <Button variant="destructive">Delete</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete user</DialogTitle>
                    <DialogDescription>
                      Permanently delete <strong>{user.username}</strong>? This action cannot be
                      undone.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setDeleteOpen(false)}>
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => deleteUser.mutate()}
                      disabled={deleteUser.isPending}
                    >
                      {deleteUser.isPending ? 'Deleting...' : 'Delete'}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </CardContent>
        </Card>

        {/* Details card */}
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">ID</dt>
                <dd className="font-mono text-foreground">{user.id}</dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Username</dt>
                <dd className="font-medium text-foreground">{user.username}</dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="text-foreground">{user.email ?? '—'}</dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">First name</dt>
                <dd className="text-foreground">{user.first_name ?? '—'}</dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Last name</dt>
                <dd className="text-foreground">{user.last_name ?? '—'}</dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Role</dt>
                <dd>
                  <Badge variant="secondary" className="capitalize">
                    {user.role}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Status</dt>
                <dd>
                  <Badge variant={user.is_active ? 'default' : 'outline'}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </dd>
              </div>
              <div className="flex justify-between border-b border-border pb-2">
                <dt className="text-muted-foreground">Must change password</dt>
                <dd className="text-foreground">{user.must_change_password ? 'Yes' : 'No'}</dd>
              </div>
              <div className="flex justify-between pb-2">
                <dt className="text-muted-foreground">Created</dt>
                <dd className="text-foreground">
                  {new Date(user.created_at).toLocaleDateString()}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Edit dialog */}
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Edit user — {user.username}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              {updateUser.isError && (
                <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                  Failed to update user
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="edit-role">Role</Label>
                <Select value={editRole} onValueChange={setEditRole}>
                  <SelectTrigger id="edit-role" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_OPTIONS.map((r) => (
                      <SelectItem key={r} value={r} className="capitalize">
                        {r.charAt(0).toUpperCase() + r.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="edit-first-name">First name</Label>
                  <Input
                    id="edit-first-name"
                    value={editFirstName}
                    onChange={(e) => setEditFirstName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="edit-last-name">Last name</Label>
                  <Input
                    id="edit-last-name"
                    value={editLastName}
                    onChange={(e) => setEditLastName(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-is-active">Status</Label>
                <Select
                  value={editIsActive ? 'active' : 'inactive'}
                  onValueChange={(v) => setEditIsActive(v === 'active')}
                >
                  <SelectTrigger id="edit-is-active" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="edit-must-change-password"
                  checked={editMustChangePassword}
                  onChange={(e) => setEditMustChangePassword(e.target.checked)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <Label htmlFor="edit-must-change-password" className="font-normal cursor-pointer">
                  Must change password on next login
                </Label>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={updateUser.isPending}>
                  {updateUser.isPending ? 'Saving...' : 'Save changes'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </AppShell>
  )
}
