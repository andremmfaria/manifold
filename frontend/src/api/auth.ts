import { client } from './client'

export type LoginPayload = { username: string; password: string }
export type PasswordPayload = { current_password: string; new_password: string }

export type MeResponse = {
  id: string
  username: string
  role: string
  mustChangePassword: boolean
}

export const authApi = {
  async login(payload: LoginPayload) {
    const response = await client.post('/api/v1/auth/login', payload)
    return response.data
  },
  async logout() {
    await client.post('/api/v1/auth/logout')
  },
  async me() {
    const response = await client.get<MeResponse>('/api/v1/auth/me')
    return response.data
  },
  async changePassword(payload: PasswordPayload) {
    await client.patch('/api/v1/auth/me/password', payload)
  },
}
