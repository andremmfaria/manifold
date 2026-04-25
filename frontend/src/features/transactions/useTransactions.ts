import { useQuery } from '@tanstack/react-query'
import { transactionsApi } from '@/api/transactions'

export function useTransactions(filters?: Record<string, string>) {
  return useQuery({ queryKey: ['transactions', filters], queryFn: () => transactionsApi.list(filters) })
}
