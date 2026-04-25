from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class ProviderConnectionContext:
    id: str
    user_id: str
    provider_type: str
    credentials: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)


@dataclass(slots=True)
class AccountData:
    provider_account_id: str
    account_type: str
    currency: str
    display_name: str | None = None
    iban: str | None = None
    sort_code: str | None = None
    account_number: str | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class BalanceData:
    account_id: str
    available: Decimal | None
    current: Decimal | None
    currency: str
    overdraft: Decimal | None = None
    credit_limit: Decimal | None = None
    as_of: datetime | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class TransactionData:
    provider_transaction_id: str
    amount: Decimal
    currency: str
    transaction_type: str
    transaction_category: str | None = None
    description: str | None = None
    merchant_name: str | None = None
    merchant_category: str | None = None
    transaction_date: str = ""
    settled_date: str | None = None
    running_balance: Decimal | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class PendingTransactionData:
    provider_transaction_id: str | None
    amount: Decimal | None
    currency: str | None
    description: str | None = None
    merchant_name: str | None = None
    transaction_date: str | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class CardData:
    provider_card_id: str
    account_provider_id: str | None = None
    display_name: str | None = None
    card_network: str | None = None
    partial_card_number: str | None = None
    currency: str | None = None
    credit_limit: Decimal | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class DirectDebitData:
    provider_mandate_id: str | None
    name: str
    status: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    frequency: str | None = None
    reference: str | None = None
    last_payment_date: str | None = None
    next_payment_date: str | None = None
    next_payment_amount: Decimal | None = None
    raw_payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class StandingOrderData:
    provider_standing_order_id: str | None
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
    raw_payload: dict = field(default_factory=dict)
