import { client } from './client'

// ── Types ─────────────────────────────────────────────────────────────────────

export type MergeRequest = {
  account_ids: string[]
}

export type MergeResponse = {
  identity_id: string
  account_ids: string[]
}

export type UnmergeRequest = {
  account_id: string
}

export type UnmergeResponse = {
  caveat: string
}

export type SuggestionItem = {
  account_a_id: string
  account_b_id: string
  score: number
  reasons: string[]
}

export type SuggestionsResponse = {
  suggestions: SuggestionItem[]
  /** Always false until Phase 5 (txn dedup) ships — do NOT render aggregated balances. */
  aggregated: false
}

export type DismissSuggestionRequest = {
  account_a_id: string
  account_b_id: string
  write_do_not_merge?: boolean
}

export type DismissSuggestionResponse = {
  dismissed: boolean
}

export type IdentityMember = {
  id: string
  user_id: string
  provider_account_id: string
  account_type: string
  currency: string
  display_name: string | null
  identity_id: string | null
  created_at: string
}

export type IdentityResponse = {
  id: string
  user_id: string
  origin: string
  master_account_id: string | null
  merged_into: string | null
  merged_at: string | null
  created_at: string
  updated_at: string
  members: IdentityMember[]
  /** Always false until Phase 5 (txn dedup) ships — do NOT render aggregated balances. */
  aggregated: false
}

// ── API functions ─────────────────────────────────────────────────────────────

export const identitiesApi = {
  async merge(payload: MergeRequest) {
    const response = await client.post<MergeResponse>('/api/v1/identities/merge', payload)
    return response.data
  },

  async unmerge(payload: UnmergeRequest) {
    const response = await client.post<UnmergeResponse>('/api/v1/identities/unmerge', payload)
    return response.data
  },

  async suggestions() {
    const response = await client.get<SuggestionsResponse>('/api/v1/identities/suggestions')
    return response.data
  },

  async dismissSuggestion(payload: DismissSuggestionRequest) {
    const response = await client.post<DismissSuggestionResponse>(
      '/api/v1/identities/suggestions/dismiss',
      payload,
    )
    return response.data
  },

  async getIdentity(identityId: string) {
    const response = await client.get<IdentityResponse>(`/api/v1/identities/${identityId}`)
    return response.data
  },
}
