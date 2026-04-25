import { client } from './client'
import type { Notifier, NotifierCreateRequest } from '../types/notifier'

export const getNotifiers = (): Promise<{ items: Notifier[]; total: number }> => 
  client.get('/api/v1/notifiers').then(r => r.data)

export const createNotifier = (data: NotifierCreateRequest): Promise<Notifier> => 
  client.post('/api/v1/notifiers', data).then(r => r.data)

export const deleteNotifier = (id: string): Promise<void> => 
  client.delete(`/api/v1/notifiers/${id}`).then(r => r.data)

export const testNotifier = (id: string): Promise<{ delivered: boolean }> => 
  client.post(`/api/v1/notifiers/${id}/test`).then(r => r.data)

export const updateNotifier = (id: string, data: Partial<NotifierCreateRequest>): Promise<Notifier> => 
  client.patch(`/api/v1/notifiers/${id}`, data).then(r => r.data)
