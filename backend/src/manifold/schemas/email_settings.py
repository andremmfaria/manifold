from __future__ import annotations

from datetime import datetime

from manifold.schemas.common import SchemaModel


class EmailSettingsResponse(SchemaModel):
    provider: str
    config: dict | None
    from_address: str | None
    from_name: str | None
    is_configured: bool
    created_at: datetime | None
    updated_at: datetime | None


class EmailSettingsUpdateRequest(SchemaModel):
    provider: str
    config: dict
    from_address: str | None = None
    from_name: str | None = None


class EmailSettingsTestRequest(SchemaModel):
    to_address: str


class SuppressionResponse(SchemaModel):
    id: str
    address_hmac: str  # hex-encoded, never plaintext
    reason: str
    source: str
    created_at: datetime


class SuppressionCreateRequest(SchemaModel):
    address: str
    reason: str = "manual"


class SuppressionListResponse(SchemaModel):
    items: list[SuppressionResponse]
    total: int
    page: int
    page_size: int


__all__ = [
    "EmailSettingsResponse",
    "EmailSettingsTestRequest",
    "EmailSettingsUpdateRequest",
    "SuppressionCreateRequest",
    "SuppressionListResponse",
    "SuppressionResponse",
]
