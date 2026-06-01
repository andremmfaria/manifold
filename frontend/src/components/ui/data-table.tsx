import * as React from 'react'
import {
  type ColumnDef,
  type ColumnOrderState,
  type ColumnSizingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ChevronDown, ChevronUp, Settings2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

// Extend ColumnMeta to allow a human-readable label used in the columns dropdown.
declare module '@tanstack/react-table' {
  interface ColumnMeta<TData, TValue> {
    label?: string
  }
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const

type StoredPrefs = {
  columnVisibility?: VisibilityState
  columnSizing?: ColumnSizingState
  columnOrder?: ColumnOrderState
  pageSize?: number
  wrap?: boolean
}

function loadPrefs(storageKey: string): StoredPrefs {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return {}
    return JSON.parse(raw) as StoredPrefs
  } catch {
    return {}
  }
}

function savePrefs(storageKey: string, prefs: StoredPrefs) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(prefs))
  } catch {
    // Storage full or unavailable — silently ignore.
  }
}

// Draft state for the preferences modal.
type DraftPrefs = {
  pageSize: number
  wrap: boolean
  columnVisibility: VisibilityState
  columnOrder: ColumnOrderState
}

interface DataTableProps<TData> {
  columns: ColumnDef<TData, any>[]
  data: TData[]
  emptyMessage?: React.ReactNode
  initialPageSize?: number
  storageKey?: string
  toolbar?: React.ReactNode
  onRowClick?: (row: TData) => void
}

export function DataTable<TData>({
  columns,
  data,
  emptyMessage = 'No data.',
  initialPageSize = 10,
  storageKey,
  toolbar,
  onRowClick,
}: DataTableProps<TData>) {
  const prefs = React.useMemo(
    () => (storageKey ? loadPrefs(storageKey) : {}),
    // We only read prefs once on mount — storageKey must not change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>(
    prefs.columnVisibility ?? {},
  )
  const [columnSizing, setColumnSizing] = React.useState<ColumnSizingState>(
    prefs.columnSizing ?? {},
  )
  const [columnOrder, setColumnOrder] = React.useState<ColumnOrderState>(prefs.columnOrder ?? [])
  const [pagination, setPagination] = React.useState({
    pageIndex: 0,
    pageSize: prefs.pageSize ?? initialPageSize,
  })
  const [wrap, setWrap] = React.useState<boolean>(prefs.wrap ?? false)

  // Modal open state.
  const [prefsOpen, setPrefsOpen] = React.useState(false)

  // Draft state — seeded from applied state when modal opens.
  const [draft, setDraft] = React.useState<DraftPrefs | null>(null)

  // Reset to first page when the dataset length changes (e.g. upstream filter applied).
  const prevDataLength = React.useRef(data.length)
  React.useEffect(() => {
    if (data.length !== prevDataLength.current) {
      prevDataLength.current = data.length
      setPagination((p) => ({ ...p, pageIndex: 0 }))
    }
  }, [data.length])

  // Persist prefs to localStorage whenever they change.
  React.useEffect(() => {
    if (!storageKey) return
    savePrefs(storageKey, {
      columnVisibility,
      columnSizing,
      columnOrder,
      pageSize: pagination.pageSize,
      wrap,
    })
  }, [storageKey, columnVisibility, columnSizing, columnOrder, pagination.pageSize, wrap])

  const table = useReactTable({
    data,
    columns,
    columnResizeMode: 'onChange',
    state: {
      columnVisibility,
      columnSizing,
      columnOrder,
      pagination,
    },
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    onColumnOrderChange: setColumnOrder,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  // Reconcile persisted columnOrder against the current column set on mount.
  // Drops stale ids (columns removed from schema) and appends new ones so the
  // applied order fed into useReactTable is always complete and correct.
  // storageKey and table are intentionally omitted: storageKey must not change
  // (contract of DataTableProps), and table is stable enough for a one-time mount reconcile.
  React.useEffect(
    () => {
      if (!storageKey) return
      const currentIds = table.getAllLeafColumns().map((c) => c.id)
      if (currentIds.length === 0) return
      setColumnOrder((stored) => {
        if (stored.length === 0) return stored // no saved prefs — leave as-is (TanStack uses default)
        const validSet = new Set(currentIds)
        const reconciled = stored.filter((id) => validSet.has(id))
        currentIds.forEach((id) => {
          if (!reconciled.includes(id)) reconciled.push(id)
        })
        return reconciled
      })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const { pageIndex, pageSize } = pagination
  const totalRows = data.length
  const firstRow = totalRows === 0 ? 0 : pageIndex * pageSize + 1
  const lastRow = Math.min((pageIndex + 1) * pageSize, totalRows)

  // Seed draft from current applied state when modal opens.
  function handleOpenChange(open: boolean) {
    if (open) {
      // Seed draft order from actual column order (or derive from table columns if not yet set).
      const currentOrder =
        columnOrder.length > 0 ? columnOrder : table.getAllLeafColumns().map((c) => c.id)
      setDraft({
        pageSize: pagination.pageSize,
        wrap,
        columnVisibility: { ...columnVisibility },
        columnOrder: [...currentOrder],
      })
    } else {
      // Cancel — discard draft.
      setDraft(null)
    }
    setPrefsOpen(open)
  }

  function handleConfirm() {
    if (!draft) return
    setWrap(draft.wrap)
    setColumnVisibility(draft.columnVisibility)
    setColumnOrder(draft.columnOrder)
    setPagination((p) => ({ ...p, pageIndex: 0, pageSize: draft.pageSize }))
    setDraft(null)
    setPrefsOpen(false)
  }

  // All leaf columns for the preferences modal (from draft order).
  const allLeafColumns = table.getAllLeafColumns()

  // Build ordered column list for modal using draft order.
  const orderedColumns = React.useMemo(() => {
    if (!draft) return []
    const colMap = new Map(allLeafColumns.map((c) => [c.id, c]))
    const ordered = draft.columnOrder
      .map((id) => colMap.get(id))
      .filter((c): c is NonNullable<typeof c> => c !== undefined)
    // Append any columns not present in draft order (new columns added after prefs saved).
    const inOrder = new Set(draft.columnOrder)
    allLeafColumns.forEach((c) => {
      if (!inOrder.has(c.id)) ordered.push(c)
    })
    return ordered
  }, [draft, allLeafColumns])

  function moveDraftColumn(index: number, direction: 'up' | 'down') {
    if (!draft) return
    // orderedColumns is the reconciled view (stale ids dropped, new columns appended).
    // Swap within that reconciled list, then derive a new draft.columnOrder from it so
    // indices stay aligned regardless of stale entries in the persisted order.
    const reordered = [...orderedColumns]
    const swapIndex = direction === 'up' ? index - 1 : index + 1
    ;[reordered[index], reordered[swapIndex]] = [reordered[swapIndex], reordered[index]]
    setDraft({ ...draft, columnOrder: reordered.map((c) => c.id) })
  }

  function setDraftVisibility(colId: string, visible: boolean) {
    if (!draft) return
    setDraft({
      ...draft,
      columnVisibility: { ...draft.columnVisibility, [colId]: visible },
    })
  }

  function getDraftVisible(col: (typeof allLeafColumns)[number]): boolean {
    if (!draft) return col.getIsVisible()
    // If not in map, default to visible (true).
    return draft.columnVisibility[col.id] !== false
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">{toolbar}</div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Preferences modal trigger */}
          <Dialog open={prefsOpen} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Settings2 className="mr-1.5 size-3.5" />
                Preferences
              </Button>
            </DialogTrigger>
            <DialogContent
              className="sm:max-w-md"
              onEscapeKeyDown={() => handleOpenChange(false)}
              onInteractOutside={() => handleOpenChange(false)}
            >
              <DialogHeader>
                <DialogTitle>Preferences</DialogTitle>
              </DialogHeader>

              {draft && (
                <div className="flex flex-col gap-5 py-1">
                  {/* Page size */}
                  <div className="flex flex-col gap-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Page size
                    </span>
                    <RadioGroup
                      value={String(draft.pageSize)}
                      onValueChange={(v) => setDraft({ ...draft, pageSize: Number(v) })}
                      className="flex flex-row flex-wrap gap-x-4 gap-y-2"
                    >
                      {PAGE_SIZE_OPTIONS.map((n) => (
                        <div key={n} className="flex items-center gap-2">
                          <RadioGroupItem value={String(n)} id={`page-size-${n}`} />
                          <Label htmlFor={`page-size-${n}`} className="font-normal cursor-pointer">
                            {n} rows
                          </Label>
                        </div>
                      ))}
                    </RadioGroup>
                  </div>

                  <Separator />

                  {/* Wrap lines */}
                  <div className="flex flex-col gap-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Wrap lines
                    </span>
                    <div className="flex items-start gap-2">
                      <Checkbox
                        id="wrap-lines"
                        checked={draft.wrap}
                        onCheckedChange={(checked) =>
                          setDraft({ ...draft, wrap: checked === true })
                        }
                        className="mt-0.5"
                      />
                      <div className="flex flex-col gap-0.5">
                        <Label htmlFor="wrap-lines" className="font-normal cursor-pointer">
                          Wrap lines
                        </Label>
                        <p className="text-xs text-muted-foreground">
                          Enable to wrap table cell content to multiple lines.
                        </p>
                      </div>
                    </div>
                  </div>

                  <Separator />

                  {/* Column preferences */}
                  <div className="flex flex-col gap-2">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Column preferences
                    </span>
                    <div className="flex flex-col gap-1">
                      {orderedColumns.map((col, idx) => {
                        const canHide = col.getCanHide()
                        const visible = getDraftVisible(col)
                        const label = (col.columnDef.meta as any)?.label ?? col.id
                        const isFirst = idx === 0
                        const isLast = idx === orderedColumns.length - 1

                        return (
                          <div
                            key={col.id}
                            className="flex items-center gap-2 rounded-md px-1 py-1 hover:bg-muted/50"
                          >
                            {/* Reorder buttons */}
                            <div className="flex flex-col">
                              <button
                                type="button"
                                aria-label={`Move ${label} up`}
                                disabled={isFirst}
                                onClick={() => moveDraftColumn(idx, 'up')}
                                className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              >
                                <ChevronUp className="size-3" />
                              </button>
                              <button
                                type="button"
                                aria-label={`Move ${label} down`}
                                disabled={isLast}
                                onClick={() => moveDraftColumn(idx, 'down')}
                                className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                              >
                                <ChevronDown className="size-3" />
                              </button>
                            </div>

                            {/* Visibility checkbox */}
                            <Checkbox
                              id={`col-vis-${col.id}`}
                              checked={visible}
                              disabled={!canHide}
                              onCheckedChange={(checked) =>
                                setDraftVisibility(col.id, checked === true)
                              }
                            />

                            {/* Column label */}
                            <Label
                              htmlFor={`col-vis-${col.id}`}
                              className={cn(
                                'flex-1 font-normal',
                                canHide ? 'cursor-pointer' : 'cursor-default opacity-60',
                              )}
                            >
                              {label}
                            </Label>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => handleOpenChange(false)}>
                  Cancel
                </Button>
                <Button variant="default" onClick={handleConfirm}>
                  Confirm
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Table */}
      <div className="relative w-full overflow-x-auto rounded-md border border-border">
        <table className="w-full caption-bottom text-sm" style={{ tableLayout: 'fixed' }}>
          <thead className="[&_tr]:border-b">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b transition-colors">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    style={{ width: header.getSize() }}
                    className={cn(
                      'relative h-10 px-2 text-left align-middle font-medium text-foreground [&:has([role=checkbox])]:pr-0',
                      wrap ? 'whitespace-normal break-words' : 'whitespace-nowrap',
                    )}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                    {/* Resize handle */}
                    {header.column.getCanResize() && (
                      <div
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        className={cn(
                          'absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none hover:bg-border active:bg-ring',
                          header.column.getIsResizing() && 'bg-ring',
                        )}
                      />
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="[&_tr:last-child]:border-0">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="p-8 text-center text-sm text-muted-foreground"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    'border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted',
                    onRowClick && 'cursor-pointer',
                  )}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      style={{ width: cell.column.getSize() }}
                      className={cn(
                        'p-2 align-middle [&:has([role=checkbox])]:pr-0',
                        wrap
                          ? 'whitespace-normal break-words'
                          : 'whitespace-nowrap overflow-hidden text-ellipsis',
                      )}
                      // Prevent row-click navigation when interacting with action cells.
                      onClick={
                        onRowClick && cell.column.id === 'actions'
                          ? (e) => e.stopPropagation()
                          : undefined
                      }
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-sm text-muted-foreground">
        <span>
          {totalRows === 0 ? 'No results' : `Showing ${firstRow}–${lastRow} of ${totalRows}`}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs">
            Page {pageIndex + 1} of {table.getPageCount() || 1}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
