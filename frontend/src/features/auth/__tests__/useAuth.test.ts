import { describe, expect, it } from 'vitest'

describe('AuthProvider exports', () => {
  it('exports useAuth hook', async () => {
    const { useAuth } = await import('@/features/auth/AuthProvider')

    expect(typeof useAuth).toBe('function')
  })

  it('exports AuthProvider component', async () => {
    const { AuthProvider } = await import('@/features/auth/AuthProvider')

    expect(typeof AuthProvider).toBe('function')
  })
})
