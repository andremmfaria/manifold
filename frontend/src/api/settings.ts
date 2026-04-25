import { client } from './client'

export const getSettings = (): Promise<any> => 
  client.get('/api/v1/settings').then(r => r.data)
