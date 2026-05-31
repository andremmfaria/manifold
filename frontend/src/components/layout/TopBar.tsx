import { useAuth } from '@/features/auth/useAuth'

export function TopBar() {
  const auth = useAuth()
  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <div className="flex items-center gap-3">
        <img alt="Manifold" className="h-8 w-8" src="/logo.svg" />
        <span className="font-semibold">Manifold</span>
      </div>
      <div className="flex items-center gap-4">
        {auth.username && (
          <span className="text-sm text-gray-500">{auth.username}</span>
        )}
        <button
          className="rounded border px-3 py-2 text-sm"
          onClick={() => {
            void auth.logout()
          }}
        >
          Logout
        </button>
      </div>
    </header>
  )
}
