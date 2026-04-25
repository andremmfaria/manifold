import { client } from './client'

export const syncRunsApi = {
  async list() {
    const response = await client.get('/api/v1/sync-runs')
    return response.data
  },
}
