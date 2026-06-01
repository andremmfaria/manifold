import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { connectionsApi, type ConnectionUpdatePayload } from '@/api/connections'

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

export function useUpdateConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      connectionId,
      payload,
    }: {
      connectionId: string
      payload: ConnectionUpdatePayload
    }) => connectionsApi.update(connectionId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['connections'] })
    },
  })
}

export function useRemoveConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (connectionId: string) => connectionsApi.remove(connectionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['connections'] })
    },
  })
}
