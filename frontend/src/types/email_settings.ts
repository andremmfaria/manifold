export interface EmailSettings {
  provider: string
  config: Record<string, unknown> | null // secrets arrive masked as "********" or null
  from_address: string | null
  from_name: string | null
  is_configured: boolean
  created_at: string | null
  updated_at: string | null
}

export interface EmailSettingsUpdateRequest {
  provider: string
  config: Record<string, unknown>
  from_address?: string | null
  from_name?: string | null
}

export interface SuppressionItem {
  id: string
  address_hmac: string
  reason: string
  source: string
  created_at: string
}

export interface SuppressionListResponse {
  items: SuppressionItem[]
  total: number
  page: number
  page_size: number
}

export interface EmailTestResult {
  ok: boolean
  message_id?: string
  error?: string
}
