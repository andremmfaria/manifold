import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { identitiesApi } from '@/api/identities'

// Shallow test: verify the API module calls the right endpoints with the right
// shape. The axios client is mocked so no network I/O occurs.

vi.mock('@/api/client', () => ({
  client: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

import { client } from '@/api/client'

const mockClient = client as unknown as {
  post: ReturnType<typeof vi.fn>
  get: ReturnType<typeof vi.fn>
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('identitiesApi', () => {
  describe('merge', () => {
    it('POST /api/v1/identities/merge with account_ids', async () => {
      const response = {
        data: { identity_id: 'id-1', account_ids: ['a', 'b'] },
      }
      mockClient.post.mockResolvedValueOnce(response)

      const result = await identitiesApi.merge({ account_ids: ['a', 'b'] })

      expect(mockClient.post).toHaveBeenCalledWith('/api/v1/identities/merge', {
        account_ids: ['a', 'b'],
      })
      expect(result).toEqual(response.data)
    })
  })

  describe('unmerge', () => {
    it('POST /api/v1/identities/unmerge with account_id', async () => {
      const response = { data: { caveat: 'Review balances after unmerge.' } }
      mockClient.post.mockResolvedValueOnce(response)

      const result = await identitiesApi.unmerge({ account_id: 'acct-1' })

      expect(mockClient.post).toHaveBeenCalledWith('/api/v1/identities/unmerge', {
        account_id: 'acct-1',
      })
      expect(result.caveat).toBe('Review balances after unmerge.')
    })
  })

  describe('suggestions', () => {
    it('GET /api/v1/identities/suggestions', async () => {
      const response = {
        data: {
          suggestions: [
            { account_a_id: 'a1', account_b_id: 'a2', score: 0.85, reasons: ['Same name'] },
          ],
          aggregated: false,
        },
      }
      mockClient.get.mockResolvedValueOnce(response)

      const result = await identitiesApi.suggestions()

      expect(mockClient.get).toHaveBeenCalledWith('/api/v1/identities/suggestions')
      expect(result.suggestions).toHaveLength(1)
      expect(result.aggregated).toBe(false)
    })
  })

  describe('dismissSuggestion', () => {
    it('POST /api/v1/identities/suggestions/dismiss with write_do_not_merge default', async () => {
      const response = { data: { dismissed: true } }
      mockClient.post.mockResolvedValueOnce(response)

      const result = await identitiesApi.dismissSuggestion({
        account_a_id: 'a1',
        account_b_id: 'a2',
        write_do_not_merge: true,
      })

      expect(mockClient.post).toHaveBeenCalledWith('/api/v1/identities/suggestions/dismiss', {
        account_a_id: 'a1',
        account_b_id: 'a2',
        write_do_not_merge: true,
      })
      expect(result.dismissed).toBe(true)
    })
  })

  describe('getIdentity', () => {
    it('GET /api/v1/identities/:id', async () => {
      const response = {
        data: {
          id: 'id-1',
          user_id: 'u-1',
          origin: 'manual',
          master_account_id: 'acct-1',
          merged_into: null,
          merged_at: null,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          members: [],
          aggregated: false,
        },
      }
      mockClient.get.mockResolvedValueOnce(response)

      const result = await identitiesApi.getIdentity('id-1')

      expect(mockClient.get).toHaveBeenCalledWith('/api/v1/identities/id-1')
      expect(result.id).toBe('id-1')
      expect(result.aggregated).toBe(false)
    })
  })
})
