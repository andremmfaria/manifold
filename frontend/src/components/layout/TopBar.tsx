import { Moon, Sun, Monitor } from 'lucide-react'
import { useAuth } from '@/features/auth/useAuth'
import { useTheme } from '@/features/theme/ThemeProvider'

function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const cycle = () => {
    if (theme === 'light') setTheme('dark')
    else if (theme === 'dark') setTheme('system')
    else setTheme('light')
  }

  const icon =
    theme === 'dark' ? <Moon className="h-4 w-4" /> :
    theme === 'light' ? <Sun className="h-4 w-4" /> :
    <Monitor className="h-4 w-4" />

  const label =
    theme === 'dark' ? 'Switch to system theme' :
    theme === 'light' ? 'Switch to dark theme' :
    'Switch to light theme'

  return (
    <button
      aria-label={label}
      className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
      onClick={cycle}
      type="button"
    >
      {icon}
    </button>
  )
}

export function TopBar() {
  const auth = useAuth()
  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-background px-6">
      <div className="flex items-center gap-3">
        <img alt="Manifold" className="h-8 w-8" src="/logo.svg" />
        <span className="font-semibold text-foreground">Manifold</span>
      </div>
      <div className="flex items-center gap-2">
        {auth.username && (
          <span className="text-sm text-muted-foreground">{auth.username}</span>
        )}
        <ThemeToggle />
        <button
          className="rounded-md border border-border px-3 py-1.5 text-sm text-foreground hover:bg-accent transition-colors"
          onClick={() => {
            void auth.logout()
          }}
          type="button"
        >
          Logout
        </button>
      </div>
    </header>
  )
}
