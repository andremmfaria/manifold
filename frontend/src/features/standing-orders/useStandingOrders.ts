import { useQuery } from '@tanstack/react-query'
import { accountsApi } from '@/api/accounts'

export function useStandingOrders(accountId: string) {
  return useQuery({ queryKey: ['standing-orders', accountId], queryFn: () => accountsApi.standingOrders(accountId) })
}
