export interface Alarm {
  id: string
  user_id: string
  name: string
  condition: object
  status: 'active' | 'paused' | 'archived'
  state: 'ok' | 'pending' | 'firing' | 'resolved' | 'muted'
  account_ids: string[]
  notifier_ids: string[]
  repeat_count: number
  for_duration_minutes: number
  cooldown_minutes: number
  notify_on_resolve: boolean
  mute_until: string | null
  last_evaluated_at: string | null
  last_fired_at: string | null
  created_at: string
  updated_at: string
}

export interface AlarmCreateRequest {
  name: string
  condition: object
  account_ids: string[]
  notifier_ids?: string[]
  repeat_count?: number
  for_duration_minutes?: number
  cooldown_minutes?: number
  notify_on_resolve?: boolean
}
