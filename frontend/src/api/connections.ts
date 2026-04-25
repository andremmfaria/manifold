import { client } from './client'

export type Connection = {
  id: string
  user_id: string
  provider_type: string
  display_name: string | null
  status: string
  auth_status: string
  consent_expires_at: string | null
  last_sync_at: string | null
}

export const connectionsApi = {
  async list() {
    const response = await client.get<Connection[]>('/api/v1/connections')
    return response.data
  },
  async get(connectionId: string) {
    const response = await client.get<Connection>(`/api/v1/connections/${connectionId}`)
    return response.data
  },
  async sync(connectionId: string) {
    const response = await client.post(`/api/v1/connections/${connectionId}/sync`)
    return response.data
  },
}
