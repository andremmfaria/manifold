import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi, type LoginPayload, type PasswordPayload } from '@/api/auth'

export type AuthContextValue = {
  isAuthenticated: boolean
  role: string | null
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
  const [mustChangePassword, setMustChangePassword] = useState(false)

  async function refreshMe() {
    try {
      const me = await authApi.me()
      setIsAuthenticated(true)
      setRole(me.role)
      setMustChangePassword(me.mustChangePassword)
    } catch {
      setIsAuthenticated(false)
      setRole(null)
      setMustChangePassword(false)
    }
  }

  useEffect(() => {
    void refreshMe()
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated,
      role,
      mustChangePassword,
      login: async (payload) => {
        await authApi.login(payload)
        await refreshMe()
      },
      logout: async () => {
        await authApi.logout()
        setIsAuthenticated(false)
        setRole(null)
        setMustChangePassword(false)
      },
      changePassword: async (payload) => {
        await authApi.changePassword(payload)
        await refreshMe()
      },
      refreshMe,
    }),
    [isAuthenticated, mustChangePassword, role],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('Auth context missing')
  return context
}
