import { client } from './client'

export type Provider = {
  type: string
  provider_type: string
  display_name: string
  auth_kind: string
  supports_pending: boolean
  supports_direct_debits: boolean
  supports_cards: boolean
  supports_standing_orders: boolean
}

export const providersApi = {
  async list() {
    const response = await client.get<Provider[]>('/api/v1/providers')
    return response.data
  },
}
