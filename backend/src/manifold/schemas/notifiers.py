from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict

from manifold.schemas.common import DeletedResponse, SchemaModel
from manifold.schemas.notification_deliveries import NotificationDeliveryResponse


class NotifierCreateRequest(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    type: str
    config: dict
    is_enabled: bool = True


class NotifierUpdateRequest(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None


class NotifierResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    type: str
    is_enabled: bool
    config: dict
    created_at: datetime
    updated_at: datetime


class NotifierListResponse(SchemaModel):
    items: list[NotifierResponse]
    total: int
    page: int
    page_size: int


class NotifierTestResponse(SchemaModel):
    ok: bool


class NotifierDeliveryListResponse(SchemaModel):
    items: list[NotificationDeliveryResponse]
    total: int
    page: int
    page_size: int


__all__ = [
    "DeletedResponse",
    "NotifierCreateRequest",
    "NotifierDeliveryListResponse",
    "NotifierListResponse",
    "NotifierResponse",
    "NotifierTestResponse",
    "NotifierUpdateRequest",
]
