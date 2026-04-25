from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class EventResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str | None = None
    user_id: str
    event_type: str
    source_type: str | None = None
    occurred_at: datetime | None = None
    recorded_at: datetime | None = None
    confidence: float | None = None
    explanation: str | None = None
    payload: dict | None = None


class EventListResponse(SchemaModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int
