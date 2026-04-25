import { cn } from "@/lib/utils"

interface StatusBadgeProps {
  status: string
  className?: string
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  ok: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-600',
  pending: 'bg-yellow-100 text-yellow-800',
  firing: 'bg-red-100 text-red-800',
  failed: 'bg-red-100 text-red-800',
  resolved: 'bg-blue-100 text-blue-800',
  muted: 'bg-gray-100 text-gray-600',
  syncing: 'bg-blue-100 text-blue-800',
  success: 'bg-green-100 text-green-800',
  delivered: 'bg-green-100 text-green-800',
  expired: 'bg-orange-100 text-orange-800',
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const color = STATUS_COLORS[status.toLowerCase()] || 'bg-gray-100 text-gray-600'

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        color,
        className
      )}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
