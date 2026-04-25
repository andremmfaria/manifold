export interface Connection {
  id: string
  user_id: string
  provider_type: string
  display_name: string | null
  status: string
  auth_status: string | null
  consent_expires_at: string | null
  last_sync_at: string | null
  created_at: string
  updated_at: string
}
