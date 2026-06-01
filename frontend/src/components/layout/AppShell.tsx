import React, { useState } from 'react'
import { Toaster } from '@/components/ui/sonner'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { Breadcrumbs } from './Breadcrumbs'

const STORAGE_KEY = 'manifold:sidebar-collapsed'

export function AppShell({ children }: { children?: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState<boolean>(
    () => typeof window !== 'undefined' && window.localStorage.getItem(STORAGE_KEY) === '1',
  )

  const toggleSidebar = () => {
    setCollapsed((prev) => {
      const next = !prev
      window.localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
      return next
    })
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <Breadcrumbs />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
      <Toaster />
    </div>
  )
}
