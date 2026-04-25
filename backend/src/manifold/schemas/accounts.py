from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict

from manifold.schemas.common import SchemaModel


class AccountResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    provider_connection_id: str
    provider_account_id: str
    account_type: str
    currency: str
    display_name: str | None
    iban: str | None
    sort_code: str | None
    account_number: str | None
    is_active: bool
    current_balance: Decimal | None = None
    balance_currency: str | None = None
    created_at: datetime
    updated_at: datetime


class BalanceResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str | None = None
    card_id: str | None = None
    current: Decimal | None = None
    available: Decimal | None = None
    currency: str | None = None
    overdraft: Decimal | None = None
    credit_limit: Decimal | None = None
    as_of: datetime | None = None
    recorded_at: datetime
    created_at: datetime


class PaginatedResponse(SchemaModel):
    items: list[object]
    total: int
    page: int
    page_size: int


class PendingTransactionResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    provider_transaction_id: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    description: str | None = None
    merchant_name: str | None = None
    transaction_date: str | None = None
    created_at: datetime


class DirectDebitResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    provider_mandate_id: str | None = None
    name: str
    status: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    frequency: str | None = None
    reference: str | None = None
    last_payment_date: str | None = None
    next_payment_date: str | None = None
    next_payment_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class StandingOrderResponse(SchemaModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    provider_standing_order_id: str | None = None
    reference: str | None = None
    status: str | None = None
    currency: str | None = None
    frequency: str | None = None
    first_payment_date: str | None = None
    first_payment_amount: Decimal | None = None
    next_payment_date: str | None = None
    next_payment_amount: Decimal | None = None
    final_payment_date: str | None = None
    final_payment_amount: Decimal | None = None
    previous_payment_date: str | None = None
    previous_payment_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class AccountListResponse(SchemaModel):
    items: list[AccountResponse]
    total: int
    page: int
    page_size: int


class BalanceListResponse(SchemaModel):
    items: list[BalanceResponse]
    total: int
    page: int
    page_size: int
