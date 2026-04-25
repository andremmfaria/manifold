import { client } from './client'
import type { Alarm, AlarmCreateRequest } from '../types/alarm'

export const getAlarms = (): Promise<{ items: Alarm[]; total: number; page: number; page_size: number }> => 
  client.get('/api/v1/alarms').then(r => r.data)

export const getAlarm = (id: string): Promise<Alarm> => 
  client.get(`/api/v1/alarms/${id}`).then(r => r.data)

export const createAlarm = (data: AlarmCreateRequest): Promise<Alarm> => 
  client.post('/api/v1/alarms', data).then(r => r.data)

export const updateAlarm = (id: string, data: Partial<AlarmCreateRequest>): Promise<Alarm> => 
  client.patch(`/api/v1/alarms/${id}`, data).then(r => r.data)

export const deleteAlarm = (id: string): Promise<void> => 
  client.delete(`/api/v1/alarms/${id}`).then(r => r.data)

export const muteAlarm = (id: string, mute_until: string): Promise<void> => 
  client.post(`/api/v1/alarms/${id}/mute`, { mute_until }).then(r => r.data)

export const unmuteAlarm = (id: string): Promise<void> => 
  client.post(`/api/v1/alarms/${id}/unmute`).then(r => r.data)

export const getAlarmHistory = (id: string): Promise<{ items: any[] }> => 
  client.get(`/api/v1/alarms/${id}/history`).then(r => r.data)

export const getAlarmFirings = (id: string): Promise<{ items: any[] }> => 
  client.get(`/api/v1/alarms/${id}/firings`).then(r => r.data)
