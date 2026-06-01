import type { ComponentType } from 'react'
import { Link } from '@tanstack/react-router'
import {
  Home,
  Plug,
  Wallet,
  ArrowLeftRight,
  Bell,
  Send,
  CreditCard,
  Repeat,
  CalendarClock,
  ShieldCheck,
  Users,
  MonitorSmartphone,
  PanelLeftClose,
} from 'lucide-react'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/features/auth/useAuth'
import { cn } from '@/lib/utils'

type NavItem = {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
  exact?: boolean
}

// Links available to members (non-superadmin) — the financial surface area.
const memberItems: NavItem[] = [
  { to: '/connections', label: 'Connections', icon: Plug },
  { to: '/accounts', label: 'Accounts', icon: Wallet },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/alarms', label: 'Alarms', icon: Bell },
  { to: '/notifiers', label: 'Notifiers', icon: Send },
  { to: '/cards', label: 'Cards', icon: CreditCard },
  { to: '/direct-debits', label: 'Direct debits', icon: Repeat },
  { to: '/standing-orders', label: 'Standing orders', icon: CalendarClock },
]

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon
  return (
    <Link
      to={item.to}
      title={collapsed ? item.label : undefined}
      activeOptions={item.exact ? { exact: true } : undefined}
      activeProps={{ className: 'bg-accent text-accent-foreground' }}
      className={cn(
        'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-accent-foreground',
        collapsed && 'justify-center px-0',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  )
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const auth = useAuth()
  // Superadmin manages users/system only — no access to financial data (the financial
  // endpoints 403 for that role), so don't surface those links.
  const isSuperadmin = auth.role === 'superadmin'

  return (
    <aside
      className={cn(
        'flex min-h-screen shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      {/* Brand + collapse toggle (h-16 matches the top bar so they line up).
          Expanded: logo + wordmark on the left, collapse button on the right.
          Collapsed: the logo itself becomes the expand toggle — no stacked button. */}
      <div className="flex h-16 items-center justify-between border-b border-border px-3">
        {collapsed ? (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            className="mx-auto rounded-md p-1 transition-colors hover:bg-accent"
          >
            <img alt="Manifold" className="h-8 w-8" src="/logo.svg" />
          </button>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <img alt="Manifold" className="h-8 w-8" src="/logo.svg" />
              <span className="font-semibold text-foreground">Manifold</span>
            </div>
            <button
              type="button"
              onClick={onToggle}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      <nav className="space-y-0.5 p-3">
        <NavLink
          item={{ to: '/', label: 'Overview', icon: Home, exact: true }}
          collapsed={collapsed}
        />
        {!isSuperadmin && (
          <>
            {memberItems.map((item) => (
              <NavLink key={item.to} item={item} collapsed={collapsed} />
            ))}
            <Separator className="my-2" />
            <NavLink
              item={{
                to: '/settings/access',
                label: 'Access',
                icon: ShieldCheck,
              }}
              collapsed={collapsed}
            />
          </>
        )}
        {isSuperadmin && (
          <NavLink
            item={{ to: '/settings/users', label: 'Users', icon: Users }}
            collapsed={collapsed}
          />
        )}
        <NavLink
          item={{
            to: '/settings/sessions',
            label: 'Sessions',
            icon: MonitorSmartphone,
          }}
          collapsed={collapsed}
        />
      </nav>
    </aside>
  )
}
