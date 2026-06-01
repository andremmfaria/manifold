import type { Account } from '@/api/accounts'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

type Props = {
  open: boolean
  accounts: Account[]
  isPending: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function MergeConfirmDialog({ open, accounts, isPending, onConfirm, onCancel }: Props) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Merge accounts?</DialogTitle>
          <DialogDescription>
            These accounts will be linked as the same physical account. The oldest account becomes
            the primary. Balances are shown per-account — combined totals arrive once transaction
            deduplication ships.
          </DialogDescription>
        </DialogHeader>

        <ul className="space-y-1.5 rounded-lg bg-muted/50 p-3 text-sm">
          {accounts.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2">
              <span className="truncate font-medium">
                {a.display_name || a.account_type.replace(/_/g, ' ')}
              </span>
              <span className="shrink-0 font-mono text-xs text-muted-foreground">
                {a.id.slice(0, 8)}…
              </span>
            </li>
          ))}
        </ul>

        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Merging…' : 'Merge'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
