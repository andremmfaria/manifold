from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class TransactionResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str | None = None
    card_id: str | None = None
    account_display_name: str | None = None
    provider_transaction_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    transaction_type: str | None = None
    transaction_category: str | None = None
    description: str | None = None
    merchant_name: str | None = None
    merchant_category: str | None = None
    transaction_date: str | None = None
    settled_date: str | None = None
    running_balance: Decimal | None = None
    status: str | None = None
    is_recurring_candidate: bool | None = None
    recurrence_profile_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TransactionListResponse(SchemaModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
