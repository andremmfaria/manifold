import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

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
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Access Management</h2>
          <p className="mt-1 text-muted-foreground">Manage who has access to your data.</p>
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            Failed to load access grants
          </div>
        )}

        <Card>
          <CardHeader className="border-b">
            <CardTitle>Active Grants</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-4 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : grants && grants.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Grantee</TableHead>
                    <TableHead>Access Level</TableHead>
                    <TableHead>Granted At</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {grants.map(grant => (
                    <TableRow key={grant.id}>
                      <TableCell className="font-medium text-foreground">{grant.grantee_username}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="capitalize">
                          {grant.access_level}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(grant.granted_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => revokeGrant.mutate(grant.id)}
                          disabled={revokeGrant.isPending}
                        >
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-8 text-center text-muted-foreground text-sm">
                You haven&apos;t granted access to anyone.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
