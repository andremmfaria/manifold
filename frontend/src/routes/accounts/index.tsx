import { useState } from 'react'
import { createRoute, redirect } from '@tanstack/react-router'
import { GitMerge } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import type { AuthContextValue } from '@/features/auth/AuthProvider'
import type { Account } from '@/api/accounts'
import { AccountCard } from '@/features/accounts/AccountCard'
import { MergeConfirmDialog } from '@/features/accounts/MergeConfirmDialog'
import { UnmergeConfirmDialog } from '@/features/accounts/UnmergeConfirmDialog'
import { MergeSuggestionsBar } from '@/features/accounts/MergeSuggestionsBar'
import { useAccounts } from '@/features/accounts/useAccounts'
import {
  useMergeAccounts,
  useUnmergeAccount,
  useMergeSuggestions,
} from '@/features/accounts/useIdentities'
import { Button } from '@/components/ui/button'
import { rootRoute } from '../__root'

export const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accounts',
  beforeLoad: ({
    context,
    location,
  }: {
    context: { auth: AuthContextValue }
    location: { href: string }
  }) => {
    if (!context.auth.isAuthenticated)
      throw redirect({ to: '/login', search: { redirect: location.href } })
  },
  component: AccountsPage,
})

// ── Identity grouping helpers ─────────────────────────────────────────────────

/**
 * Build a map of identity_id → account[] from the accounts list.
 * Only groups accounts that have an identity_id (requires backend to expose the field).
 */
function buildIdentityGroups(accounts: Account[]): Map<string, Account[]> {
  const map = new Map<string, Account[]>()
  for (const account of accounts) {
    if (account.identity_id) {
      const group = map.get(account.identity_id) ?? []
      group.push(account)
      map.set(account.identity_id, group)
    }
  }
  return map
}

/** Identity groups with ≥2 members (actually merged). */
function mergedGroups(groups: Map<string, Account[]>): Map<string, Account[]> {
  const result = new Map<string, Account[]>()
  for (const [id, members] of groups) {
    if (members.length >= 2) result.set(id, members)
  }
  return result
}

// ── Page ──────────────────────────────────────────────────────────────────────

function AccountsPage() {
  const { data: accounts = [], isLoading } = useAccounts()
  const { data: suggestionsData } = useMergeSuggestions()
  const suggestions = suggestionsData?.suggestions ?? []

  const merge = useMergeAccounts()
  const unmerge = useUnmergeAccount()

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Merge dialog state
  const [mergeOpen, setMergeOpen] = useState(false)
  const [pendingMergeIds, setPendingMergeIds] = useState<string[]>([])

  // Unmerge dialog state
  const [unmergeOpen, setUnmergeOpen] = useState(false)
  const [unmergeAccount, setUnmergeAccount] = useState<Account | null>(null)
  const [unmergeCaveat, setUnmergeCaveat] = useState<string | null>(null)

  // Derived
  const identityGroups = buildIdentityGroups(accounts)
  const merged = mergedGroups(identityGroups)

  // Per-account lookup helpers
  const isAccountMerged = (a: Account) =>
    !!a.identity_id && (merged.get(a.identity_id)?.length ?? 0) >= 2

  // Selection helpers
  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function exitSelectionMode() {
    setSelectionMode(false)
    setSelectedIds(new Set())
  }

  // Trigger merge confirm from selection
  function openMergeFromSelection() {
    if (selectedIds.size < 2) return
    setPendingMergeIds([...selectedIds])
    setMergeOpen(true)
  }

  // Trigger merge confirm from suggestion banner
  function openMergeFromSuggestion(accountIds: string[]) {
    setPendingMergeIds(accountIds)
    setMergeOpen(true)
  }

  function confirmMerge() {
    merge.mutate(
      { account_ids: pendingMergeIds },
      {
        onSuccess: () => {
          setMergeOpen(false)
          setPendingMergeIds([])
          exitSelectionMode()
        },
      },
    )
  }

  function openUnmerge(account: Account) {
    setUnmergeCaveat(null)
    setUnmergeAccount(account)
    setUnmergeOpen(true)
  }

  function confirmUnmerge() {
    if (!unmergeAccount) return
    unmerge.mutate(
      { account_id: unmergeAccount.id },
      {
        onSuccess: (data) => {
          // Keep dialog open to show the caveat from §13.4.
          setUnmergeCaveat(data.caveat)
        },
      },
    )
  }

  function closeUnmerge() {
    setUnmergeOpen(false)
    setUnmergeAccount(null)
    setUnmergeCaveat(null)
  }

  const pendingMergeAccounts = accounts.filter((a) => pendingMergeIds.includes(a.id))

  return (
    <AppShell>
      <div className="space-y-6 p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Accounts</h1>
            <p className="mt-1 text-muted-foreground">
              Canonical accounts with latest derived balance.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {selectionMode ? (
              <>
                <span className="text-sm text-muted-foreground">{selectedIds.size} selected</span>
                <Button
                  size="sm"
                  onClick={openMergeFromSelection}
                  disabled={selectedIds.size < 2 || merge.isPending}
                >
                  <GitMerge className="h-4 w-4" />
                  Merge
                </Button>
                <Button size="sm" variant="outline" onClick={exitSelectionMode}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSelectionMode(true)}
                disabled={accounts.length < 2}
              >
                <GitMerge className="h-4 w-4" />
                Select to merge
              </Button>
            )}
          </div>
        </div>

        {/* Merge suggestions */}
        {suggestions.length > 0 && (
          <MergeSuggestionsBar
            suggestions={suggestions}
            accounts={accounts}
            onMerge={openMergeFromSuggestion}
          />
        )}

        {/* §8 / §13.6 gate notice — shown when merged groups exist */}
        {merged.size > 0 && (
          <p className="text-xs text-muted-foreground">
            Linked accounts are shown individually. Combined totals will be available once
            transaction deduplication ships.
          </p>
        )}

        {/* Account grid */}
        {isLoading ? (
          <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="rounded-xl bg-card ring-1 ring-foreground/10 p-4 space-y-3 animate-pulse"
              >
                <div className="h-4 w-2/3 rounded bg-muted" />
                <div className="h-3 w-1/2 rounded bg-muted" />
                <div className="h-8 w-1/3 rounded bg-muted mt-4" />
              </div>
            ))}
          </div>
        ) : (
          <AccountGrid
            accounts={accounts}
            merged={merged}
            selectionMode={selectionMode}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
            isAccountMerged={isAccountMerged}
            onUnmerge={openUnmerge}
          />
        )}
      </div>

      {/* Merge confirm dialog */}
      <MergeConfirmDialog
        open={mergeOpen}
        accounts={pendingMergeAccounts}
        isPending={merge.isPending}
        onConfirm={confirmMerge}
        onCancel={() => {
          setMergeOpen(false)
          setPendingMergeIds([])
        }}
      />

      {/* Unmerge confirm dialog */}
      <UnmergeConfirmDialog
        open={unmergeOpen}
        accountName={unmergeAccount?.display_name || unmergeAccount?.account_type || ''}
        caveat={unmergeCaveat}
        isPending={unmerge.isPending}
        onConfirm={confirmUnmerge}
        onCancel={closeUnmerge}
      />
    </AppShell>
  )
}

// ── Account grid sub-component ────────────────────────────────────────────────

type GridProps = {
  accounts: Account[]
  merged: Map<string, Account[]>
  selectionMode: boolean
  selectedIds: Set<string>
  onToggleSelect: (id: string) => void
  isAccountMerged: (a: Account) => boolean
  onUnmerge: (a: Account) => void
}

/**
 * Renders accounts grouped by identity when possible.
 * Groups with ≥2 members get a visual bracket; singletons render flat.
 *
 * Grouping is gated on accounts having `identity_id` in the API response.
 * Until the backend exposes that field, all accounts render as singletons.
 */
function AccountGrid({
  accounts,
  merged,
  selectionMode,
  selectedIds,
  onToggleSelect,
  isAccountMerged,
  onUnmerge,
}: GridProps) {
  const rendered = new Set<string>()
  const sections: React.ReactNode[] = []

  // Emit merged groups first
  for (const [identityId, members] of merged) {
    sections.push(
      <div key={`group-${identityId}`} className="col-span-full space-y-2">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Same account &middot; {members.length} linked
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 rounded-xl border border-primary/20 p-3 bg-primary/[0.02]">
          {members.map((a) => {
            rendered.add(a.id)
            return (
              <AccountCard
                key={a.id}
                account={a}
                selectionMode={selectionMode}
                selected={selectedIds.has(a.id)}
                onToggleSelect={onToggleSelect}
                isMerged={isAccountMerged(a)}
                isMaster={false}
                onUnmerge={onUnmerge}
              />
            )
          })}
        </div>
      </div>,
    )
  }

  // Emit remaining (unmerged) accounts
  const singletons = accounts.filter((a) => !rendered.has(a.id))
  sections.push(
    ...singletons.map((a) => (
      <AccountCard
        key={a.id}
        account={a}
        selectionMode={selectionMode}
        selected={selectedIds.has(a.id)}
        onToggleSelect={onToggleSelect}
        isMerged={false}
        isMaster={false}
        onUnmerge={onUnmerge}
      />
    )),
  )

  return <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">{sections}</div>
}
