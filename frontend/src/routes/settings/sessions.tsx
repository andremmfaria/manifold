import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Monitor, Smartphone, Globe } from 'lucide-react'

export const settingsSessionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings/sessions',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (!context.auth.isAuthenticated) throw redirect({ to: '/login' })
    if (context.auth.mustChangePassword) throw redirect({ to: '/change-password' })
  },
  component: SessionsPage,
})

interface Session {
  id: string
  user_agent: string
  created_at: string
  last_seen_at: string
  is_current: boolean
}

function getDeviceIcon(userAgent: string) {
  const ua = userAgent.toLowerCase()
  if (ua.includes('mobile') || ua.includes('android') || ua.includes('iphone')) {
    return <Smartphone className="h-5 w-5 text-muted-foreground" />
  }
  if (ua.includes('mac') || ua.includes('windows') || ua.includes('linux')) {
    return <Monitor className="h-5 w-5 text-muted-foreground" />
  }
  return <Globe className="h-5 w-5 text-muted-foreground" />
}

function parseUserAgent(userAgent: string) {
  // Simple heuristic parsing
  const ua = userAgent.toLowerCase()
  let browser = 'Unknown Browser'
  let os = 'Unknown OS'
  
  if (ua.includes('firefox')) browser = 'Firefox'
  else if (ua.includes('chrome')) browser = 'Chrome'
  else if (ua.includes('safari')) browser = 'Safari'
  else if (ua.includes('edge')) browser = 'Edge'
  
  if (ua.includes('windows')) os = 'Windows'
  else if (ua.includes('mac')) os = 'macOS'
  else if (ua.includes('linux')) os = 'Linux'
  else if (ua.includes('android')) os = 'Android'
  else if (ua.includes('iphone') || ua.includes('ipad')) os = 'iOS'

  return `${browser} on ${os}`
}

function SessionsPage() {
  const queryClient = useQueryClient()

  const { data: sessions, isLoading, error } = useQuery<Session[]>({
    queryKey: ['sessions'],
    queryFn: () => client.get('/api/v1/auth/sessions').then(res => res.data),
  })

  const revokeSession = useMutation({
    mutationFn: (sessionId: string) => client.delete(`/api/v1/auth/sessions/${sessionId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })

  const revokeOthers = useMutation({
    mutationFn: () => client.post('/api/v1/auth/sessions/revoke-others', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })

  const activeSessions = sessions?.filter(s => !s.is_current) || []
  const currentSession = sessions?.find(s => s.is_current)

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Active Sessions</h2>
            <p className="mt-1 text-muted-foreground">Manage the devices that are currently logged in to your account.</p>
          </div>
          {activeSessions.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => revokeOthers.mutate()}
              disabled={revokeOthers.isPending}
            >
              Sign out of all other devices
            </Button>
          )}
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-4 text-sm text-destructive">
            Failed to load sessions
          </div>
        )}

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ) : (
          <div className="space-y-4">
            {currentSession && (
              <Card className="border-primary/30 bg-primary/5 dark:bg-primary/10">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-4">
                    <div className="rounded-full bg-primary/10 p-2.5 shrink-0">
                      {getDeviceIcon(currentSession.user_agent)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-foreground">
                          {parseUserAgent(currentSession.user_agent)}
                        </p>
                        <Badge variant="default" className="text-xs">
                          Current Device
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground font-mono truncate">
                        {currentSession.user_agent}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Signed in: {new Date(currentSession.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {activeSessions.map((session) => (
              <Card key={session.id}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-4 min-w-0">
                      <div className="rounded-full bg-muted p-2.5 shrink-0">
                        {getDeviceIcon(session.user_agent)}
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-foreground">
                          {parseUserAgent(session.user_agent)}
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground font-mono truncate">
                          {session.user_agent}
                        </p>
                        <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                          <span>Signed in: {new Date(session.created_at).toLocaleDateString()}</span>
                          <span>Last active: {new Date(session.last_seen_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => revokeSession.mutate(session.id)}
                      disabled={revokeSession.isPending}
                      className="shrink-0"
                    >
                      Sign out
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
