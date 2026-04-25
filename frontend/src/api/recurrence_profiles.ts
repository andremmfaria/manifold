import { client } from './client'

export const getRecurrenceProfiles = (): Promise<any> => 
  client.get('/api/v1/recurrence-profiles').then(r => r.data)
