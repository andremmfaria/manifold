import { cn } from "@/lib/utils"

interface ConfidenceIndicatorProps {
  confidence: number | null
  showLabel?: boolean
  className?: string
}

export function ConfidenceIndicator({ confidence, showLabel = true, className }: ConfidenceIndicatorProps) {
  if (confidence === null || confidence === undefined) {
    return <span className="text-gray-400 text-xs">-</span>
  }

  const percentage = Math.round(confidence * 100)
  
  let colorClass = 'bg-red-500'
  if (confidence >= 0.75) {
    colorClass = 'bg-green-500'
  } else if (confidence >= 0.5) {
    colorClass = 'bg-yellow-500'
  }

  const bars = 5
  const activeBars = Math.round(confidence * bars)

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex gap-[1px]">
        {Array.from({ length: bars }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-3 w-1.5 rounded-sm",
              i < activeBars ? colorClass : "bg-gray-200"
            )}
          />
        ))}
      </div>
      {showLabel && (
        <span className="text-xs font-medium text-gray-600">
          {percentage}%
        </span>
      )}
    </div>
  )
}
