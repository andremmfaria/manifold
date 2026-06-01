import { FormEvent, useEffect, useState } from 'react'
import { createRoute, redirect, useNavigate, useSearch } from '@tanstack/react-router'
import { rootRoute } from './__root'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAuth } from '@/features/auth/useAuth'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

/** Guard against open-redirect: only allow same-origin paths. */
function isSafeRedirect(url: string): boolean {
  return url.startsWith('/') && !url.startsWith('//') && !url.includes(':')
}

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  validateSearch: (search: Record<string, unknown>) => ({
    redirect: typeof search.redirect === 'string' ? search.redirect : undefined,
  }),
  beforeLoad: ({
    context,
    search,
  }: {
    context: { auth: AuthContextValue }
    search: { redirect?: string }
  }) => {
    if (context.auth.isAuthenticated) {
      // Forward the redirect param so a mid-session link-open still lands correctly.
      const to = search.redirect && isSafeRedirect(search.redirect) ? search.redirect : '/'
      throw redirect({ to })
    }
  },
  component: LoginPage,
})

function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const { redirect: redirectTo } = useSearch({ from: loginRoute.id })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Redirect once auth state has propagated to the router context (avoids navigating with a
  // stale context that would bounce straight back to /login).
  useEffect(() => {
    if (!auth.isAuthenticated) return
    if (auth.mustChangePassword) {
      void navigate({ to: '/change-password' })
      return
    }
    // Restore original URL if it is a safe internal path, otherwise fall back to root.
    const destination = redirectTo && isSafeRedirect(redirectTo) ? redirectTo : '/'
    void navigate({ to: destination })
  }, [auth.isAuthenticated, auth.mustChangePassword, navigate, redirectTo])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      setError(null)
      await auth.login({ username, password })
    } catch {
      setError('Login failed')
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* ── Left: form panel ── */}
      <main className="flex flex-1 flex-col items-center justify-center bg-background px-6 py-12 lg:max-w-[45%]">
        <div className="w-full max-w-[360px]">
          {/* Logo + wordmark */}
          <div className="mb-8 flex items-center gap-2.5">
            <img src="/logo.svg" alt="Manifold logo" className="h-8 w-8" />
            <span className="text-lg font-semibold tracking-tight text-foreground">Manifold</span>
          </div>

          {/* Heading */}
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Sign in</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Welcome back. Enter your credentials to continue.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Email or username</Label>
              <Input
                id="username"
                placeholder="Email or username"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" size="lg" className="mt-1 w-full">
              Sign in
            </Button>
          </form>
        </div>
      </main>

      {/* ── Right: brand panel (desktop only) ── */}
      <aside
        aria-hidden="true"
        className="hidden lg:flex lg:flex-1 lg:flex-col lg:items-center lg:justify-center lg:relative lg:overflow-hidden"
        style={{
          background:
            'linear-gradient(135deg, oklch(0.18 0.04 186) 0%, oklch(0.22 0.06 186) 40%, oklch(0.28 0.09 190) 100%)',
        }}
      >
        {/* Dot-grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'radial-gradient(circle, oklch(0.85 0.06 186) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />

        {/* Teal radial glow */}
        <div
          className="absolute inset-0 opacity-20"
          style={{
            background:
              'radial-gradient(ellipse 70% 60% at 60% 50%, oklch(0.511 0.086 186.4) 0%, transparent 70%)',
          }}
        />

        {/* Content */}
        <div className="relative z-10 max-w-sm px-8 text-center">
          <div className="mb-6 flex justify-center">
            <img src="/logo.svg" alt="" className="h-12 w-12 opacity-90" />
          </div>
          <h2 className="text-3xl font-semibold leading-tight tracking-tight text-white">
            Sync everything.
            <br />
            Observe anything.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/60">
            Manifold connects your data sources, keeps them in sync, and surfaces what matters —
            alarms, trends, and observability signals in one place.
          </p>

          {/* Feature pills */}
          <ul className="mt-8 flex flex-col gap-2.5 text-left">
            {[
              'Real-time data sync across providers',
              'Smart alarms with confidence scoring',
              'Unified observability dashboard',
            ].map((feat) => (
              <li key={feat} className="flex items-center gap-2.5 text-sm text-white/70">
                <span
                  className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
                  style={{ background: 'oklch(0.65 0.10 186)' }}
                />
                {feat}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
