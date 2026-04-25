import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'

export const settingsAccessRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/access',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: AccessPage,
})

interface AccessGrant {
  id: string
  grantee_username: string
  access_level: string
  granted_at: string
}

function AccessPage() {
  const queryClient = useQueryClient()

  const { data: grants, isLoading, error } = useQuery<AccessGrant[]>({
    queryKey: ['access-grants'],
    queryFn: () => client.get('/api/v1/users/me/access').then(res => res.data),
  })

  const revokeGrant = useMutation({
    mutationFn: (grantId: string) => client.delete(`/api/v1/users/me/access/${grantId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['access-grants'] })
    },
  })

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Access Management</h2>
          <p className="text-slate-500">Manage who has access to your data.</p>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            Failed to load access grants
          </div>
        )}

        <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
          <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
            <span className="font-medium text-sm text-slate-700">Active Grants</span>
          </div>
          
          {isLoading ? (
            <div className="p-4 space-y-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : grants && grants.length > 0 ? (
            <table className="w-full text-sm text-left">
              <thead className="bg-slate-50/50 text-slate-500 border-b">
                <tr>
                  <th className="px-4 py-3 font-medium">Grantee</th>
                  <th className="px-4 py-3 font-medium">Access Level</th>
                  <th className="px-4 py-3 font-medium">Granted At</th>
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {grants.map(grant => (
                  <tr key={grant.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900">{grant.grantee_username}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                        {grant.access_level}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {new Date(grant.granted_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => revokeGrant.mutate(grant.id)}
                        disabled={revokeGrant.isPending}
                        className="text-red-600 hover:text-red-800 font-medium text-sm disabled:opacity-50 transition-colors"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-500 text-sm">
              <p>You haven't granted access to anyone.</p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
