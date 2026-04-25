import { ObservabilityTag } from '@/components/ObservabilityTag'
import { ConfidenceIndicator } from '@/components/ConfidenceIndicator'

interface PredictionBadgeProps {
  sourceType: 'observed' | 'predicted' | string
  confidence?: number | null
}

export function PredictionBadge({ sourceType, confidence }: PredictionBadgeProps) {
  if (sourceType === 'observed') {
    return <ObservabilityTag sourceType="observed" />
  }

  if (sourceType === 'predicted') {
    return (
      <div className="flex items-center gap-2">
        <ObservabilityTag sourceType="predicted" />
        <ConfidenceIndicator confidence={confidence ?? null} />
      </div>
    )
  }

  return <ObservabilityTag sourceType={sourceType} />
}
