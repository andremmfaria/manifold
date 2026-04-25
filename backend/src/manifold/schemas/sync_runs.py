from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class SyncRunResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_connection_id: str | None = None
    account_id: str | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    accounts_synced: int | None = None
    transactions_synced: int | None = None
    new_transactions: int | None = None
    error_code: str | None = None
    error_detail: dict | None = None
    created_at: datetime


class SyncRunListResponse(SchemaModel):
    items: list[SyncRunResponse]
    total: int
    page: int
    page_size: int
