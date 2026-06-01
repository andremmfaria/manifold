import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { identitiesApi } from '@/api/identities'
import type { DismissSuggestionRequest, MergeRequest, UnmergeRequest } from '@/api/identities'

export function useMergeSuggestions() {
  return useQuery({
    queryKey: ['identities', 'suggestions'],
    queryFn: identitiesApi.suggestions,
  })
}

export function useMergeAccounts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: MergeRequest) => identitiesApi.merge(payload),
    onSuccess: () => {
      toast.success('Accounts merged successfully')
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['identities', 'suggestions'] })
    },
    onError: () => {
      toast.error('Failed to merge accounts')
    },
  })
}

export function useUnmergeAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: UnmergeRequest) => identitiesApi.unmerge(payload),
    onSuccess: () => {
      toast.success('Account unmerged successfully')
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['identities', 'suggestions'] })
    },
    onError: () => {
      toast.error('Failed to unmerge account')
    },
  })
}

export function useDismissSuggestion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: DismissSuggestionRequest) => identitiesApi.dismissSuggestion(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['identities', 'suggestions'] })
    },
    onError: () => {
      toast.error('Failed to dismiss suggestion')
    },
  })
}
