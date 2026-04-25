from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel
from manifold.schemas.sync_runs import SyncRunResponse


class ConnectionCreateRequest(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    provider_type: str
    display_name: str | None = None
    credentials: dict | None = None
    config: dict | None = None


class ConnectionUpdateRequest(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None = None
    status: str | None = None
    auth_status: str | None = None
    credentials: dict | None = None
    config: dict | None = None


class ConnectionResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    provider_type: str
    display_name: str | None = None
    status: str
    auth_status: str
    config: dict
    consent_expires_at: datetime | None = None
    last_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ConnectionAuthUrlResponse(SchemaModel):
    auth_url: str


class ConnectionSyncResponse(SchemaModel):
    sync_run_id: str
    status: str


class ConnectionSyncRunListResponse(SchemaModel):
    items: list[SyncRunResponse]
    total: int
    page: int
    page_size: int
