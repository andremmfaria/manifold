export interface DashboardSummary {
  accounts_total: number
  active_alarms_count: number
  last_sync_at: string | null
  recent_events: Array<{ event_type: string; source_type: string; account_id: string; occurred_at: string }>
  upcoming_debits: Array<{ profile_id: string; label: string | null; next_predicted_at: string; amount_mean: string | null; confidence: number | null }>
}
