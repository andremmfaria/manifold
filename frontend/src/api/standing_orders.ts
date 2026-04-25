import { client } from './client'

export interface StandingOrder {
  id: string
  account_id: string
  provider_standing_order_id: string | null
  payee_name: string | null
  reference: string | null
  amount: string | null
  currency: string | null
  frequency: string | null
  next_payment_date: string | null
  status: string | null
  created_at: string
  updated_at: string
}

export const standingOrdersApi = {
  async listForAccount(accountId: string): Promise<StandingOrder[]> {
    const r = await client.get<StandingOrder[]>(`/api/v1/accounts/${accountId}/standing-orders`)
    return r.data
  },
}
