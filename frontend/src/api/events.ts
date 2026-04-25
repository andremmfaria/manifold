import { client } from './client'

export const eventsApi = {
  async list() {
    const response = await client.get('/api/v1/events')
    return response.data
  },
}
