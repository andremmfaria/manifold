export function ConnectionStatusBadge({ status }: { status: string }) {
  const color =
    status === 'active'
      ? 'bg-emerald-100 text-emerald-800'
      : status === 'error'
        ? 'bg-rose-100 text-rose-800'
        : 'bg-slate-100 text-slate-700'
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${color}`}>{status}</span>
}
