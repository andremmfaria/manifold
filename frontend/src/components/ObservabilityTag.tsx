import { cn } from "@/lib/utils"

interface ObservabilityTagProps {
  sourceType: 'observed' | 'inferred' | 'predicted' | string
  className?: string
}

export function ObservabilityTag({ sourceType, className }: ObservabilityTagProps) {
  let color = 'bg-gray-100 text-gray-600'
  let label = sourceType
  
  if (sourceType.toLowerCase() === 'observed') {
    color = 'bg-green-100 text-green-800'
    label = 'Observed'
  } else if (sourceType.toLowerCase() === 'inferred') {
    color = 'bg-blue-100 text-blue-800'
    label = 'Inferred'
  } else if (sourceType.toLowerCase() === 'predicted') {
    color = 'bg-purple-100 text-purple-800'
    label = 'Predicted'
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold",
        color,
        className
      )}
    >
      {label}
    </span>
  )
}
