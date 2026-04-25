import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export function BalanceHistoryChart({ data }: { data: Array<{ recorded_at: string; current: string | null }> }) {
  const chartData = data.map((item) => ({
    recorded_at: new Date(item.recorded_at).toLocaleDateString(),
    current: item.current ? Number(item.current) : null,
  }))
  return (
    <div className="h-72 rounded-xl border bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
          <XAxis dataKey="recorded_at" />
          <YAxis />
          <Tooltip />
          <Area type="monotone" dataKey="current" stroke="#0f766e" fill="#99f6e4" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
