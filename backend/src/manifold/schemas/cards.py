from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class CardResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider_connection_id: str
    account_id: str | None = None
    provider_card_id: str | None = None
    display_name: str | None = None
    card_network: str | None = None
    partial_card_number: str | None = None
    currency: str | None = None
    credit_limit: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class CardListResponse(SchemaModel):
    items: list[CardResponse]
    total: int
    page: int
    page_size: int
