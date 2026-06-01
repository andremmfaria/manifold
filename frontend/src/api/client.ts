import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

export const client = axios.create({
  baseURL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// The auth cookies are httpOnly (unreadable by JS), so we keep a tiny localStorage flag to
// know whether a session *might* exist. It lets a never-logged-in visitor skip the /auth/me
// and /auth/refresh probes entirely — no noisy 401s before the redirect to /login.
const SESSION_HINT_KEY = 'manifold.session'

export const hasSessionHint = (): boolean => {
  try {
    return localStorage.getItem(SESSION_HINT_KEY) === '1'
  } catch {
    return false
  }
}

export const setSessionHint = (): void => {
  try {
    localStorage.setItem(SESSION_HINT_KEY, '1')
  } catch {
    /* storage unavailable — ignore */
  }
}

export const clearSessionHint = (): void => {
  try {
    localStorage.removeItem(SESSION_HINT_KEY)
  } catch {
    /* storage unavailable — ignore */
  }
}

// Requests that must never themselves trigger a token refresh (avoids recursion / pointless calls).
const NO_REFRESH_PATHS = ['/api/v1/auth/refresh', '/api/v1/auth/login', '/api/v1/auth/logout']
const isNoRefreshPath = (url?: string): boolean =>
  !!url && NO_REFRESH_PATHS.some((path) => url.includes(path))

let refreshing: Promise<void> | null = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    // Attempt a single silent refresh only when a session may exist and this isn't an auth call.
    if (
      status === 401 &&
      original &&
      !original._retry &&
      !isNoRefreshPath(original.url) &&
      hasSessionHint()
    ) {
      original._retry = true
      refreshing ??= client
        .post('/api/v1/auth/refresh')
        .then(() => undefined)
        .catch((refreshError) => {
          // Refresh failed — the session is gone; stop probing on future loads.
          clearSessionHint()
          throw refreshError
        })
        .finally(() => {
          refreshing = null
        })
      await refreshing
      return client(original)
    }
    throw error
  },
)
