import { client } from './client'

export interface User {
  id: string
  username: string
  role: string
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

export interface CreateUserRequest {
  username: string
  password: string
  role: 'regular' | 'superadmin'
  must_change_password?: boolean
}

export const usersApi = {
  async list(): Promise<User[]> {
    const r = await client.get<User[]>('/api/v1/users')
    return r.data
  },
  async create(data: CreateUserRequest): Promise<User> {
    const r = await client.post<User>('/api/v1/users', data)
    return r.data
  },
  async deactivate(userId: string): Promise<void> {
    await client.patch(`/api/v1/users/${userId}`, { is_active: false })
  },
  async listAccessGrants(): Promise<any[]> {
    const r = await client.get('/api/v1/users/me/access')
    return r.data
  },
  async revokeGrant(grantId: string): Promise<void> {
    await client.delete(`/api/v1/users/me/access/${grantId}`)
  },
}
