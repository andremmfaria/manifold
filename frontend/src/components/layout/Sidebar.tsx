import { Link } from '@tanstack/react-router'
import { useAuth } from '@/features/auth/useAuth'

const linkClass = 'block rounded px-3 py-2 hover:bg-slate-100'

export function Sidebar() {
  const auth = useAuth()
  // Superadmin manages users/system only — no access to financial data (the financial
  // endpoints 403 for that role), so don't surface those links.
  const isSuperadmin = auth.role === 'superadmin'
  return (
    <aside className="min-h-[calc(100vh-4rem)] w-64 border-r bg-white p-4">
      <nav className="space-y-2">
        <Link className={linkClass} to="/">Overview</Link>
        {!isSuperadmin && (
          <>
            <Link className={linkClass} to="/dashboard">Dashboard</Link>
            <Link className={linkClass} to="/connections">Connections</Link>
            <Link className={linkClass} to="/accounts">Accounts</Link>
            <Link className={linkClass} to="/transactions">Transactions</Link>
            <Link className={linkClass} to="/alarms">Alarms</Link>
            <Link className={linkClass} to="/notifiers">Notifiers</Link>
            <Link className={linkClass} to="/cards">Cards</Link>
            <Link className={linkClass} to="/direct-debits">Direct debits</Link>
            <Link className={linkClass} to="/standing-orders">Standing orders</Link>
            <Link className={linkClass} to="/settings/access">Access</Link>
          </>
        )}
        {isSuperadmin && (
          <Link className={linkClass} to="/settings/users">Users</Link>
        )}
        <Link className={linkClass} to="/settings/sessions">Sessions</Link>
      </nav>
    </aside>
  )
}
