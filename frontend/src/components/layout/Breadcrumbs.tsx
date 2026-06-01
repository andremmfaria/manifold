import { Fragment } from 'react'
import { Link, useRouterState } from '@tanstack/react-router'
import { ChevronRight, Home } from 'lucide-react'

// Maps a path segment to its human label. Segments not listed fall back to a
// title-cased version of the raw value (covers dynamic ids like /accounts/abc123).
const SEGMENT_LABELS: Record<string, string> = {
  connections: 'Connections',
  connect: 'Connect',
  accounts: 'Accounts',
  transactions: 'Transactions',
  alarms: 'Alarms',
  new: 'New',
  notifiers: 'Notifiers',
  cards: 'Cards',
  'direct-debits': 'Direct debits',
  'standing-orders': 'Standing orders',
  settings: 'Settings',
  users: 'Users',
  access: 'Access',
  sessions: 'Sessions',
}

function labelFor(segment: string): string {
  // Known route slugs get a friendly label; anything else (dynamic ids like a
  // hyphenated UUID) is shown verbatim so dashes are preserved.
  return SEGMENT_LABELS[segment] ?? segment
}

export function Breadcrumbs() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const segments = pathname.split('/').filter(Boolean)

  // Build cumulative paths so each crumb links to its own level.
  const crumbs = segments.map((segment, i) => ({
    label: labelFor(segment),
    to: '/' + segments.slice(0, i + 1).join('/'),
  }))

  return (
    <nav aria-label="Breadcrumb" className="border-b border-border bg-background px-6 py-3">
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
        <li className="flex items-center">
          <Link
            to="/"
            className="flex items-center gap-1.5 hover:text-foreground transition-colors"
          >
            <Home className="h-3.5 w-3.5" />
            <span>Overview</span>
          </Link>
        </li>
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1
          return (
            <Fragment key={crumb.to}>
              <li aria-hidden="true" className="flex items-center">
                <ChevronRight className="h-3.5 w-3.5" />
              </li>
              <li className="flex items-center">
                {isLast ? (
                  <span className="font-medium text-foreground" aria-current="page">
                    {crumb.label}
                  </span>
                ) : (
                  <Link to={crumb.to} className="hover:text-foreground transition-colors">
                    {crumb.label}
                  </Link>
                )}
              </li>
            </Fragment>
          )
        })}
      </ol>
    </nav>
  )
}
