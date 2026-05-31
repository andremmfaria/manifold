import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { authApi, type LoginPayload, type PasswordPayload } from '@/api/auth'
import { clearSessionHint, hasSessionHint, setSessionHint } from '@/api/client'

export type AuthContextValue = {
  isAuthenticated: boolean
  role: string | null
  username: string | null
  firstName: string | null
  lastName: string | null
  mustChangePassword: boolean
  login: (payload: LoginPayload) => Promise<void>
  logout: () => Promise<void>
  changePassword: (payload: PasswordPayload) => Promise<void>
  refreshMe: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [role, setRole] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [firstName, setFirstName] = useState<string | null>(null)
  const [lastName, setLastName] = useState<string | null>(null)
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const queryClient = useQueryClient()

  function setUnauthenticated() {
    setIsAuthenticated(false)
    setRole(null)
    setUsername(null)
    setFirstName(null)
    setLastName(null)
    setMustChangePassword(false)
  }

  async function refreshMe() {
    // No prior session → don't probe the API at all; just send the user to /login.
    if (!hasSessionHint()) {
      setUnauthenticated()
      return
    }
    try {
      const me = await authApi.me()
      setSessionHint()
      setIsAuthenticated(true)
      setRole(me.role)
      setUsername(me.username)
      setFirstName(me.first_name)
      setLastName(me.last_name)
      setMustChangePassword(me.mustChangePassword)
    } catch {
      clearSessionHint()
      setUnauthenticated()
    }
  }

  useEffect(() => {
    void refreshMe()
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated,
      role,
      username,
      firstName,
      lastName,
      mustChangePassword,
      login: async (payload) => {
        // Drop any cached query data from a previous session before the new
        // user loads, so user B never sees user A's accounts/transactions/etc.
        queryClient.clear()
        await authApi.login(payload)
        setSessionHint()
        await refreshMe()
      },
      logout: async () => {
        await authApi.logout()
        clearSessionHint()
        setUnauthenticated()
        // Wipe cached query data on the way out so the next user starts clean.
        queryClient.clear()
      },
      changePassword: async (payload) => {
        await authApi.changePassword(payload)
        await refreshMe()
      },
      refreshMe,
    }),
    [isAuthenticated, mustChangePassword, role, username, firstName, lastName, queryClient],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('Auth context missing')
  return context
}
