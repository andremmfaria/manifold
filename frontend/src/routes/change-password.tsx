import { FormEvent, useEffect, useState } from 'react'
import { createRoute, useNavigate } from '@tanstack/react-router'
import { rootRoute } from './__root'
import { useAuth } from '@/features/auth/useAuth'

export const changePasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/change-password',
  component: ChangePasswordPage,
})

function ChangePasswordPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Redirect once auth state has propagated to the router context (avoids navigating with a
  // stale context that would bounce straight back to /change-password).
  useEffect(() => {
    if (!auth.isAuthenticated || auth.mustChangePassword) return
    void navigate({ to: '/' })
  }, [auth.isAuthenticated, auth.mustChangePassword, navigate])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      setError(null)
      await auth.changePassword({ current_password: currentPassword, new_password: newPassword })
    } catch {
      setError('Password change failed')
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-xl bg-white p-8 shadow">
        <h1 className="mb-6 text-2xl font-semibold">Change password</h1>
        <input className="mb-4 w-full rounded border p-3" type="password" placeholder="Current password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
        <input className="mb-4 w-full rounded border p-3" type="password" placeholder="New password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
        {error ? <p className="mb-4 text-sm text-red-600">{error}</p> : null}
        <button className="w-full rounded bg-teal-700 px-4 py-3 text-white" type="submit">Update</button>
      </form>
    </main>
  )
}
