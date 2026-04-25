export interface Card {
  id: string
  provider_connection_id: string
  provider_card_id: string | null
  card_type: string | null
  display_name: string | null
  currency: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CardBalance {
  id: string
  card_id: string
  current: string | null
  available: string | null
  currency: string | null
  retrieved_at: string | null
}
