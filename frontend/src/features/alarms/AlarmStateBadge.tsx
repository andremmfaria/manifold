export function AlarmStateBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    ok: 'bg-green-100 text-green-800 border-green-200',
    pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    firing: 'bg-red-100 text-red-800 border-red-200',
    resolved: 'bg-blue-100 text-blue-800 border-blue-200',
    muted: 'bg-gray-100 text-gray-800 border-gray-200',
  }
  const color = colors[state] || 'bg-gray-100 text-gray-800 border-gray-200'

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      {state.toUpperCase()}
    </span>
  )
}
