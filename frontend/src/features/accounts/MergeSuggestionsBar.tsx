import { useState } from 'react'
import { GitMerge, X } from 'lucide-react'
import type { Account } from '@/api/accounts'
import type { SuggestionItem } from '@/api/identities'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { useDismissSuggestion } from './useIdentities'

type Props = {
  suggestions: SuggestionItem[]
  accounts: Account[]
  /** Called when the user clicks "Merge" on a suggestion — pre-fills selection. */
  onMerge: (accountIds: string[]) => void
}

function accountLabel(accounts: Account[], id: string): string {
  const a = accounts.find((x) => x.id === id)
  return a?.display_name || a?.account_type.replace(/_/g, ' ') || id.slice(0, 8) + '…'
}

export function MergeSuggestionsBar({ suggestions, accounts, onMerge }: Props) {
  const dismiss = useDismissSuggestion()
  const [writeDnm, setWriteDnm] = useState<Record<string, boolean>>({})

  if (suggestions.length === 0) return null

  function pairKey(s: SuggestionItem) {
    return `${s.account_a_id}:${s.account_b_id}`
  }

  return (
    <div className="space-y-2">
      {suggestions.map((s) => {
        const key = pairKey(s)
        const isDismissing = dismiss.isPending
        const useDnm = writeDnm[key] ?? true

        return (
          <div
            key={key}
            className="flex flex-col gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-2 text-sm font-medium">
                <GitMerge className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <span className="truncate">
                  {accountLabel(accounts, s.account_a_id)}
                  <span className="mx-1.5 text-muted-foreground">&amp;</span>
                  {accountLabel(accounts, s.account_b_id)}
                </span>
                <Badge variant="outline" className="ml-auto shrink-0 font-mono text-xs">
                  {Math.round(s.score * 100)}% match
                </Badge>
              </div>
              {s.reasons.length > 0 && (
                <p className="text-xs text-muted-foreground">{s.reasons.join(' · ')}</p>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onMerge([s.account_a_id, s.account_b_id])}
                disabled={isDismissing}
              >
                Merge
              </Button>

              {/* Dismiss — with optional do_not_merge toggle */}
              <div className="flex items-center gap-1.5">
                <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
                  <Checkbox
                    checked={useDnm}
                    onCheckedChange={(v) => setWriteDnm((prev) => ({ ...prev, [key]: v === true }))}
                    disabled={isDismissing}
                  />
                  Never suggest again
                </label>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label="Dismiss suggestion"
                  disabled={isDismissing}
                  onClick={() =>
                    dismiss.mutate({
                      account_a_id: s.account_a_id,
                      account_b_id: s.account_b_id,
                      write_do_not_merge: useDnm,
                    })
                  }
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
