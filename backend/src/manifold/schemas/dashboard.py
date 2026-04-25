from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class UpcomingDebitItem(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: str
    label: str | None = None
    next_predicted_at: datetime | None = None
    amount_mean: Decimal | None = None
    confidence: float | None = None


class RecentEventItem(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: str
    source_type: str | None = None
    account_id: str | None = None
    occurred_at: datetime | None = None


class DashboardSummaryResponse(SchemaModel):
    accounts_total: int
    active_alarms_count: int
    last_sync_at: datetime | None = None
    recent_events: list[RecentEventItem]
    upcoming_debits: list[UpcomingDebitItem]
