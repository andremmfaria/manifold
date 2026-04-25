import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAlarms, getAlarm, createAlarm, updateAlarm, deleteAlarm, muteAlarm, unmuteAlarm } from '@/api/alarms'

export function useAlarms() {
  return useQuery({ queryKey: ['alarms'], queryFn: getAlarms })
}

export function useAlarm(id: string) {
  return useQuery({ queryKey: ['alarms', id], queryFn: () => getAlarm(id) })
}

export function useCreateAlarm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createAlarm,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alarms'] })
  })
}

export function useUpdateAlarm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateAlarm>[1] }) => updateAlarm(id, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['alarms'] })
      qc.invalidateQueries({ queryKey: ['alarms', id] })
    }
  })
}

export function useDeleteAlarm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAlarm,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alarms'] })
  })
}

export function useMuteAlarm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, mute_until }: { id: string; mute_until: string }) => muteAlarm(id, mute_until),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['alarms'] })
      qc.invalidateQueries({ queryKey: ['alarms', id] })
    }
  })
}

export function useUnmuteAlarm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: unmuteAlarm,
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['alarms'] })
      qc.invalidateQueries({ queryKey: ['alarms', id] })
    }
  })
}
