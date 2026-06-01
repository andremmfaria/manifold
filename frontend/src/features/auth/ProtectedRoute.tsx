import { Navigate } from '@tanstack/react-router'
import { useAuth } from './useAuth'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  if (!auth.isAuthenticated)
    return (
      <Navigate
        to="/login"
        search={{ redirect: window.location.pathname + window.location.search }}
      />
    )
  if (auth.mustChangePassword) return <Navigate to="/change-password" />
  return <>{children}</>
}
