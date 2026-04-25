import { Link } from '@tanstack/react-router'
import { useAuth } from '@/features/auth/useAuth'

export function Sidebar() {
  const auth = useAuth()
  return (
    <aside className="min-h-[calc(100vh-4rem)] w-64 border-r bg-white p-4">
      <nav className="space-y-2">
        <Link className="block rounded px-3 py-2 hover:bg-slate-100" to="/">Overview</Link>
        {auth.role === 'superadmin' ? (
          <Link className="block rounded px-3 py-2 hover:bg-slate-100" to="/settings/users">Users</Link>
        ) : (
          <Link className="block rounded px-3 py-2 hover:bg-slate-100" to="/settings/access">Access</Link>
        )}
        <Link className="block rounded px-3 py-2 hover:bg-slate-100" to="/settings/sessions">Sessions</Link>
      </nav>
    </aside>
  )
}
