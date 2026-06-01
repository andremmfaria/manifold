import { client } from "./client";

export type Connection = {
  id: string;
  user_id: string;
  provider_type: string;
  display_name: string | null;
  status: string;
  auth_status: string;
  config: Record<string, unknown>;
  consent_expires_at: string | null;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ConnectionCreatePayload = {
  provider_type: string;
  display_name?: string | null;
  config?: Record<string, unknown>;
  credentials?: Record<string, unknown>;
};

export type ConnectionUpdatePayload = {
  display_name?: string | null;
  config?: Record<string, unknown>;
};

export type SyncRun = {
  id: string;
  provider_connection_id: string;
  account_id: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  accounts_synced: number | null;
  transactions_synced: number | null;
  new_transactions: number | null;
  error_code: string | null;
  error_detail: unknown | null;
  created_at: string;
};

export const connectionsApi = {
  async list() {
    const response = await client.get<Connection[]>("/api/v1/connections");
    return response.data;
  },
  async get(connectionId: string) {
    const response = await client.get<Connection>(
      `/api/v1/connections/${connectionId}`,
    );
    return response.data;
  },
  async create(payload: ConnectionCreatePayload) {
    const response = await client.post<Connection>(
      "/api/v1/connections",
      payload,
    );
    return response.data;
  },
  async getAuthUrl(connectionId: string) {
    const response = await client.get<{ auth_url: string }>(
      `/api/v1/connections/${connectionId}/auth-url`,
    );
    return response.data;
  },
  async update(connectionId: string, payload: ConnectionUpdatePayload) {
    const response = await client.patch<Connection>(
      `/api/v1/connections/${connectionId}`,
      payload,
    );
    return response.data;
  },
  async sync(connectionId: string) {
    const response = await client.post(
      `/api/v1/connections/${connectionId}/sync`,
    );
    return response.data;
  },
  async syncRuns(connectionId: string) {
    const response = await client.get<SyncRun[]>(
      `/api/v1/connections/${connectionId}/sync-runs`,
    );
    return response.data;
  },
  async remove(connectionId: string) {
    await client.delete(`/api/v1/connections/${connectionId}`);
  },
};
