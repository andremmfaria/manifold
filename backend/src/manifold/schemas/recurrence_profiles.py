from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class RecurrenceProfileResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    label: str | None = None
    merchant_pattern: str | None = None
    amount_mean: Decimal | None = None
    amount_stddev: Decimal | None = None
    cadence_days: int | None = None
    cadence_stddev: float | None = None
    confidence: float | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    next_predicted_at: datetime | None = None
    next_predicted_amount: Decimal | None = None
    status: str | None = None
    data_source: str | None = None
    created_at: datetime
    updated_at: datetime


class RecurrenceProfileListResponse(SchemaModel):
    items: list[RecurrenceProfileResponse]
    total: int
    page: int
    page_size: int
