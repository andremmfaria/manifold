from pydantic import BaseModel


class ProviderTypeResponse(BaseModel):
    type: str
    supports_pending: bool
    supports_direct_debits: bool
    supports_cards: bool
    supports_standing_orders: bool
