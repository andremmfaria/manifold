import { client } from './client'

export interface DirectDebit {
  id: string
  account_id: string
  provider_direct_debit_id: string | null
  name: string | null
  status: string | null
  previous_payment_amount: string | null
  previous_payment_date: string | null
  created_at: string
  updated_at: string
}

export const directDebitsApi = {
  async listForAccount(accountId: string): Promise<DirectDebit[]> {
    const r = await client.get<DirectDebit[]>(`/api/v1/accounts/${accountId}/direct-debits`)
    return r.data
  },
}
