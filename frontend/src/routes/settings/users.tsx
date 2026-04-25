import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '@/api/client'
import { useState } from 'react'
import { StatusBadge } from '@/components/StatusBadge'
import { Skeleton } from '@/components/ui/skeleton'

export const settingsUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/users',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
    if (context.auth.role !== 'superadmin') throw redirect({ to: '/settings/access' })
  },
  component: UsersPage,
})

interface User {
  id: string
  username: string
  role: string
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

function UsersPage() {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('user')
  const [mustChangePassword, setMustChangePassword] = useState(true)

  const { data: users, isLoading, error } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => client.get('/api/v1/users').then(res => res.data),
  })

  const createUser = useMutation({
    mutationFn: () => client.post('/api/v1/users', { username, password, role, must_change_password: mustChangePassword }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setUsername('')
      setPassword('')
      setRole('user')
      setMustChangePassword(true)
    },
  })

  const deactivateUser = useMutation({
    mutationFn: (id: string) => client.patch(`/api/v1/users/${id}`, { is_active: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Users</h2>
          <p className="text-slate-500">Manage system users (Superadmin only).</p>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            Failed to load users
          </div>
        )}

        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-medium text-sm text-slate-700">
            User List
          </div>
          {isLoading ? (
            <div className="p-4 space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50 text-slate-500 border-b">
                <tr>
                  <th className="px-4 py-3 font-medium">Username</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {users?.map(user => (
                  <tr key={user.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900">{user.username}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={user.is_active ? 'active' : 'inactive'} />
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {user.is_active && (
                        <button
                          onClick={() => deactivateUser.mutate(user.id)}
                          disabled={deactivateUser.isPending}
                          className="text-red-600 hover:text-red-800 font-medium text-xs disabled:opacity-50"
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {(!users || users.length === 0) && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-medium text-sm text-slate-700">
            Create User
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              createUser.mutate()
            }}
            className="p-4 space-y-4"
          >
            {createUser.isError && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                Failed to create user
              </div>
            )}
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Username</label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Password</label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="superadmin">Superadmin</option>
                </select>
              </div>
            </div>
            
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="must-change-password"
                checked={mustChangePassword}
                onChange={(e) => setMustChangePassword(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="must-change-password" className="text-sm text-slate-700">
                Must change password on first login
              </label>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={createUser.isPending}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
              >
                {createUser.isPending ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  )
}
