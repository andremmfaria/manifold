import { describe, expect, it } from 'vitest'

import { client } from '@/api/client'

describe('API client', () => {
  it('has withCredentials set to true', () => {
    expect(client.defaults.withCredentials).toBe(true)
  })

  it('has correct Content-Type header', () => {
    const headers = client.defaults.headers as Record<string, any>

    expect(headers['Content-Type'] ?? headers.common?.['Content-Type']).toBe(
      'application/json',
    )
  })
})
