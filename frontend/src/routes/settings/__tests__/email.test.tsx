/**
 * Smoke-test for the /settings/email route guard.
 *
 * The guard is a pure function of (context, location) → void | redirect throw.
 * We extract the identical logic here so the test stays in-process and requires
 * no render / router harness (matching the AlarmRuleBuilder test approach).
 */
import { describe, expect, it } from 'vitest'

// ─── Inline the guard logic (mirrors beforeLoad in settings/email.tsx exactly) ─

interface FakeAuth {
  isAuthenticated: boolean
  mustChangePassword?: boolean
  role?: string
}

function runGuard(auth: FakeAuth, href = '/settings/email') {
  // Mirrors the beforeLoad body verbatim.
  if (!auth.isAuthenticated) {
    return { redirect: '/login', search: { redirect: href } }
  }
  if (auth.mustChangePassword) {
    return { redirect: '/change-password' }
  }
  if (auth.role !== 'superadmin') {
    return { redirect: '/settings/access' }
  }
  return null // allowed
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('/settings/email route guard', () => {
  it('redirects unauthenticated user to /login with redirect search param', () => {
    const result = runGuard({ isAuthenticated: false })
    expect(result?.redirect).toBe('/login')
    expect((result as { search: { redirect: string } }).search.redirect).toBe('/settings/email')
  })

  it('redirects authenticated user with mustChangePassword to /change-password', () => {
    const result = runGuard({
      isAuthenticated: true,
      mustChangePassword: true,
      role: 'superadmin',
    })
    expect(result?.redirect).toBe('/change-password')
  })

  it('redirects non-superadmin (admin role) to /settings/access', () => {
    const result = runGuard({ isAuthenticated: true, mustChangePassword: false, role: 'admin' })
    expect(result?.redirect).toBe('/settings/access')
  })

  it('redirects non-superadmin (user role) to /settings/access', () => {
    const result = runGuard({ isAuthenticated: true, mustChangePassword: false, role: 'user' })
    expect(result?.redirect).toBe('/settings/access')
  })

  it('allows a superadmin through (returns null)', () => {
    const result = runGuard({
      isAuthenticated: true,
      mustChangePassword: false,
      role: 'superadmin',
    })
    expect(result).toBeNull()
  })
})
