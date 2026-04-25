import { useQuery } from '@tanstack/react-query'
import { accountsApi } from '@/api/accounts'

export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: accountsApi.list })
}

export function useAccount(accountId: string) {
  return useQuery({ queryKey: ['accounts', accountId], queryFn: () => accountsApi.get(accountId) })
}

export function useBalanceHistory(accountId: string) {
  return useQuery({ queryKey: ['accounts', accountId, 'balances'], queryFn: () => accountsApi.balances(accountId) })
}
