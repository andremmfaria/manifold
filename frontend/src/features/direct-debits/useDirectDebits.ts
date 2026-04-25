import { useQuery } from '@tanstack/react-query'
import { accountsApi } from '@/api/accounts'

export function useDirectDebits(accountId: string) {
  return useQuery({ queryKey: ['direct-debits', accountId], queryFn: () => accountsApi.directDebits(accountId) })
}
