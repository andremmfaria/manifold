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
  accountName: string
  /**
   * The caveat string returned by the unmerge API — surfaces the "review
   * balances after unmerge" notice from §13.4.
   * Null while the dialog is in the pre-confirm state.
   */
  caveat: string | null
  isPending: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function UnmergeConfirmDialog({
  open,
  accountName,
  caveat,
  isPending,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Unmerge "{accountName}"?</DialogTitle>
          <DialogDescription>
            This account will be separated from its current identity group. A "do not merge"
            assertion will be written so it is not re-linked automatically.
          </DialogDescription>
        </DialogHeader>

        {/* Show the API caveat once the unmerge has completed (post-success notice). */}
        {caveat && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-700 dark:text-amber-400">
            {caveat}
          </div>
        )}

        {!caveat && (
          <DialogFooter>
            <Button variant="outline" onClick={onCancel} disabled={isPending}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
              {isPending ? 'Unmerging…' : 'Unmerge'}
            </Button>
          </DialogFooter>
        )}

        {caveat && (
          <DialogFooter>
            <Button onClick={onCancel}>Done</Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
