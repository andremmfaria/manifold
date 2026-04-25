from __future__ import annotations

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class ProviderTypeResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    supports_pending: bool
    supports_direct_debits: bool
    supports_cards: bool
    supports_standing_orders: bool


class ProviderCallbackResponse(SchemaModel):
    status: str
    redirect: str
