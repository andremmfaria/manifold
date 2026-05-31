import { FormEvent, useEffect, useState } from 'react'
import { createRoute, redirect, useNavigate } from '@tanstack/react-router'
import { rootRoute } from './__root'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import { useAuth } from '@/features/auth/useAuth'

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: ({ context }: { context: { auth: AuthContextValue } }) => {
    if (context.auth.isAuthenticated) throw redirect({ to: '/' })
  },
  component: LoginPage,
})

function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Redirect once auth state has propagated to the router context (avoids navigating with a
  // stale context that would bounce straight back to /login).
  useEffect(() => {
    if (!auth.isAuthenticated) return
    void navigate({ to: auth.mustChangePassword ? '/change-password' : '/' })
  }, [auth.isAuthenticated, auth.mustChangePassword, navigate])

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
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-xl bg-white p-8 shadow">
        <h1 className="mb-6 text-2xl font-semibold">Sign in</h1>
        <label className="mb-4 block">
          <span className="mb-2 block text-sm font-medium">Email or username</span>
          <input className="w-full rounded border p-3" placeholder="Email or username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="mb-4 block">
          <span className="mb-2 block text-sm font-medium">Password</span>
          <input className="w-full rounded border p-3" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}
        <button className="w-full rounded bg-teal-700 px-4 py-3 text-white" type="submit">Login</button>
      </form>
    </main>
  )
}
