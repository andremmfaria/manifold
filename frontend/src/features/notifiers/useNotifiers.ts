import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getNotifiers, createNotifier, updateNotifier, deleteNotifier, testNotifier } from '@/api/notifiers'

export function useNotifiers() {
  return useQuery({ queryKey: ['notifiers'], queryFn: getNotifiers })
}

export function useCreateNotifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createNotifier,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifiers'] })
  })
}

export function useUpdateNotifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateNotifier>[1] }) => updateNotifier(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifiers'] })
  })
}

export function useDeleteNotifier() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteNotifier,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifiers'] })
  })
}

export function useTestNotifier() {
  return useMutation({
    mutationFn: testNotifier,
  })
}
