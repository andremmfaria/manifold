import { createRoute, redirect } from '@tanstack/react-router'
import { rootRoute } from '../__root'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { client } from '@/api/client'
import { Skeleton } from '@/components/ui/skeleton'
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
  last_used_at: string
  is_current: boolean
}

function getDeviceIcon(userAgent: string) {
  const ua = userAgent.toLowerCase()
  if (ua.includes('mobile') || ua.includes('android') || ua.includes('iphone')) {
    return <Smartphone className="h-5 w-5 text-slate-400" />
  }
  if (ua.includes('mac') || ua.includes('windows') || ua.includes('linux')) {
    return <Monitor className="h-5 w-5 text-slate-400" />
  }
  return <Globe className="h-5 w-5 text-slate-400" />
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
            <h2 className="text-2xl font-semibold tracking-tight">Active Sessions</h2>
            <p className="text-slate-500">Manage the devices that are currently logged in to your account.</p>
          </div>
          {activeSessions.length > 0 && (
            <button
              onClick={() => revokeOthers.mutate()}
              disabled={revokeOthers.isPending}
              className="rounded-md bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              Sign out of all other devices
            </button>
          )}
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            Failed to load sessions
          </div>
        )}

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 w-full rounded-lg" />
            <Skeleton className="h-24 w-full rounded-lg" />
          </div>
        ) : (
          <div className="space-y-4">
            {currentSession && (
              <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="rounded-full bg-blue-100 p-2.5">
                      {getDeviceIcon(currentSession.user_agent)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-slate-900">
                          {parseUserAgent(currentSession.user_agent)}
                        </p>
                        <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                          Current Device
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-500 font-mono">
                        {currentSession.user_agent}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Signed in: {new Date(currentSession.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeSessions.map((session) => (
              <div key={session.id} className="rounded-lg border bg-white p-4 shadow-sm transition-shadow hover:border-slate-300">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="rounded-full bg-slate-100 p-2.5">
                      {getDeviceIcon(session.user_agent)}
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">
                        {parseUserAgent(session.user_agent)}
                      </p>
                      <p className="mt-1 text-sm text-slate-500 font-mono">
                        {session.user_agent}
                      </p>
                      <div className="mt-2 flex items-center gap-4 text-xs text-slate-500">
                        <span>Signed in: {new Date(session.created_at).toLocaleDateString()}</span>
                        <span>Last active: {new Date(session.last_used_at).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => revokeSession.mutate(session.id)}
                    disabled={revokeSession.isPending}
                    className="text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50 transition-colors px-3 py-2 -mr-3 -mt-2"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
