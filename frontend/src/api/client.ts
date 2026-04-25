import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const client = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

let refreshing: Promise<void> | null = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original?._retry) {
      original._retry = true
      refreshing ??= client.post('/api/v1/auth/refresh').then(() => undefined).finally(() => {
        refreshing = null
      })
      await refreshing
      return client(original)
    }
    throw error
  },
)
