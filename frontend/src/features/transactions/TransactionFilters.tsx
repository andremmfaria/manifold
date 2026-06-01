import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { DateRangeFilter, type DateRange } from '@/components/DateRangeFilter'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type Props = {
  accountId: string
  onChange: (next: string) => void
  range: DateRange
  onRangeChange: (next: DateRange) => void
  currency: string
  onCurrencyChange: (next: string) => void
  currencyOptions: string[]
  status: string
  onStatusChange: (next: string) => void
  statusOptions: string[]
}

export function TransactionFilters({
  accountId,
  onChange,
  range,
  onRangeChange,
  currency,
  onCurrencyChange,
  currencyOptions,
  status,
  onStatusChange,
  statusOptions,
}: Props) {
  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              className="pl-8"
              defaultValue={accountId}
              onChange={(event) => onChange(event.target.value)}
              placeholder="Filter by account ID…"
            />
          </div>
          <Select value={currency} onValueChange={onCurrencyChange}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Currency" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All currencies</SelectItem>
              {currencyOptions.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={onStatusChange}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All statuses</SelectItem>
              {statusOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DateRangeFilter range={range} onChange={onRangeChange} idPrefix="tx" />
        </div>
      </CardContent>
    </Card>
  )
}
