import { client } from './client'

export type Account = {
  id: string
  display_name: string | null
  account_type: string
  currency: string
  current_balance: string | null
  balance_currency: string | null
}

export const accountsApi = {
  async list() {
    const response = await client.get<Account[]>('/api/v1/accounts')
    return response.data
  },
  async get(accountId: string) {
    const response = await client.get<Account>(`/api/v1/accounts/${accountId}`)
    return response.data
  },
  async balances(accountId: string) {
    const response = await client.get(`/api/v1/accounts/${accountId}/balances`)
    return response.data
  },
  async transactions(accountId: string) {
    const response = await client.get(`/api/v1/accounts/${accountId}/transactions`)
    return response.data
  },
  async directDebits(accountId: string) {
    const response = await client.get(`/api/v1/accounts/${accountId}/direct-debits`)
    return response.data
  },
  async standingOrders(accountId: string) {
    const response = await client.get(`/api/v1/accounts/${accountId}/standing-orders`)
    return response.data
  },
}
