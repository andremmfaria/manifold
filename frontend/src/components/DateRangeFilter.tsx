import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export type DateRange = { from: string; to: string }

function fmt(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Range from `n` days ago through today, as yyyy-mm-dd strings. */
export function lastNDays(n: number): DateRange {
  const to = new Date()
  const from = new Date()
  from.setDate(from.getDate() - n)
  return { from: fmt(from), to: fmt(to) }
}

/** Whether an ISO/date string falls within the (inclusive) range. */
export function inRange(value: string | null | undefined, range: DateRange): boolean {
  if (!value) return false
  const ts = new Date(value).getTime()
  if (Number.isNaN(ts)) return false
  const fromTs = range.from ? new Date(`${range.from}T00:00:00`).getTime() : null
  const toTs = range.to ? new Date(`${range.to}T23:59:59.999`).getTime() : null
  if (fromTs != null && ts < fromTs) return false
  if (toTs != null && ts > toTs) return false
  return true
}

export function DateRangeFilter({
  range,
  onChange,
  idPrefix,
}: {
  range: DateRange
  onChange: (next: DateRange) => void
  idPrefix: string
}) {
  return (
    <div className="flex items-end gap-2">
      <div className="space-y-1">
        <Label htmlFor={`${idPrefix}-from`} className="text-xs text-muted-foreground">
          From
        </Label>
        <Input
          id={`${idPrefix}-from`}
          type="date"
          value={range.from}
          max={range.to || undefined}
          onChange={(e) => onChange({ ...range, from: e.target.value })}
          className="w-[9.5rem]"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${idPrefix}-to`} className="text-xs text-muted-foreground">
          To
        </Label>
        <Input
          id={`${idPrefix}-to`}
          type="date"
          value={range.to}
          min={range.from || undefined}
          onChange={(e) => onChange({ ...range, to: e.target.value })}
          className="w-[9.5rem]"
        />
      </div>
    </div>
  )
}
