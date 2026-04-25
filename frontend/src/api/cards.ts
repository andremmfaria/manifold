import { client } from './client'

export const cardsApi = {
  async list() {
    const response = await client.get('/api/v1/cards')
    return response.data
  },
  async get(cardId: string) {
    const response = await client.get(`/api/v1/cards/${cardId}`)
    return response.data
  },
}
