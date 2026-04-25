import { useQuery } from '@tanstack/react-query'
import { getAlarmHistory } from '@/api/alarms'
import { AlarmStateBadge } from './AlarmStateBadge'

export function AlarmHistory({ alarmId }: { alarmId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['alarms', alarmId, 'history'],
    queryFn: () => getAlarmHistory(alarmId),
  })

  if (isLoading) return <div className="text-sm text-slate-500">Loading history...</div>
  if (!data?.items?.length) return <div className="text-sm text-slate-500">No history available</div>

  return (
    <div className="overflow-x-auto rounded-lg border bg-white">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Evaluated At</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Result</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">State Transition</th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">Explanation</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 bg-white">
          {data.items.map((item, i) => (
            <tr key={i}>
              <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-900">
                {new Date(item.evaluated_at).toLocaleString()}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-sm">
                <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${item.result === 'PASS' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {item.result}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-sm">
                <div className="flex items-center gap-2">
                  <AlarmStateBadge state={item.previous_state} />
                  <span className="text-slate-400">→</span>
                  <AlarmStateBadge state={item.new_state} />
                </div>
              </td>
              <td className="px-4 py-3 text-sm text-slate-500">
                {item.explanation || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
