import { client } from './client'
import type {
  EmailSettings,
  EmailSettingsUpdateRequest,
  SuppressionListResponse,
  SuppressionItem,
  EmailTestResult,
} from '../types/email_settings'

export const getEmailSettings = (): Promise<EmailSettings> =>
  client.get('/api/v1/email-settings').then((r) => r.data)

export const updateEmailSettings = (data: EmailSettingsUpdateRequest): Promise<EmailSettings> =>
  client.put('/api/v1/email-settings', data).then((r) => r.data)

export const testEmailSettings = (toAddress: string): Promise<EmailTestResult> =>
  client.post('/api/v1/email-settings/test', { to_address: toAddress }).then((r) => r.data)

export const listSuppressions = (page = 1): Promise<SuppressionListResponse> =>
  client.get('/api/v1/email-settings/suppressions', { params: { page } }).then((r) => r.data)

export const addSuppression = (address: string, reason = 'manual'): Promise<SuppressionItem> =>
  client.post('/api/v1/email-settings/suppressions', { address, reason }).then((r) => r.data)

export const removeSuppression = (id: string): Promise<void> =>
  client.delete(`/api/v1/email-settings/suppressions/${id}`).then((r) => r.data)
