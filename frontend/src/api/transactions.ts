import { client } from './client'

export const transactionsApi = {
  async list(params?: Record<string, string>) {
    const response = await client.get('/api/v1/transactions', { params })
    return response.data
  },
}
