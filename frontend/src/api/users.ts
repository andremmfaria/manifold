import { client } from './client'

export interface User {
  id: string
  username: string
  email: string | null
  first_name: string | null
  last_name: string | null
  role: string
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

export interface CreateUserRequest {
  username: string
  password: string
  role: string
  email?: string | null
  first_name?: string | null
  last_name?: string | null
  must_change_password?: boolean
}

export interface UpdateUserRequest {
  is_active?: boolean
  role?: string
  first_name?: string | null
  last_name?: string | null
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
  async get(userId: string): Promise<User> {
    const r = await client.get<User>(`/api/v1/users/${userId}`)
    return r.data
  },
  async update(userId: string, data: UpdateUserRequest): Promise<User> {
    const r = await client.patch<User>(`/api/v1/users/${userId}`, data)
    return r.data
  },
  async remove(userId: string): Promise<void> {
    await client.delete(`/api/v1/users/${userId}`)
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
