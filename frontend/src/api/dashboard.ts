import { client } from './client'
import type { DashboardSummary } from '../types/dashboard'

export const getDashboardSummary = (): Promise<DashboardSummary> => 
  client.get('/api/v1/dashboard/summary').then(r => r.data)
