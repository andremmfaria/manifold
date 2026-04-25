import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { connectionsApi } from '@/api/connections'

export function useConnections() {
  return useQuery({ queryKey: ['connections'], queryFn: connectionsApi.list })
}

export function useSyncConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (connectionId: string) => connectionsApi.sync(connectionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['connections'] })
    },
  })
}
