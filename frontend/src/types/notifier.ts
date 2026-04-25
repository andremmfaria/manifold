export interface Notifier {
  id: string
  user_id: string
  name: string
  type: 'email' | 'webhook' | 'slack' | 'telegram'
  config: Record<string, unknown>
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface NotifierCreateRequest {
  name: string
  type: string
  config: Record<string, unknown>
  is_enabled?: boolean
}
