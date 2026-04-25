from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class NotificationDeliveryResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alarm_firing_event_id: str | None = None
    notifier_id: str | None = None
    user_id: str | None = None
    notification_type: str
    status: str
    attempt_count: int
    rendered_subject: str | None = None
    rendered_body: str | None = None
    error_message: str | None = None
    created_at: datetime
    first_attempted_at: datetime | None = None
    last_attempted_at: datetime | None = None
    delivered_at: datetime | None = None


class NotificationDeliveryListResponse(SchemaModel):
    items: list[NotificationDeliveryResponse]
    total: int
    page: int
    page_size: int
