import { client } from './client'

export const getNotificationDeliveries = (): Promise<any> => 
  client.get('/api/v1/notification-deliveries').then(r => r.data)
