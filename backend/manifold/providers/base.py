from __future__ import annotations

from abc import ABC, abstractmethod

from manifold.providers.auth.base import BaseProviderAuth
from manifold.providers.types import (
    AccountData,
    BalanceData,
    CardData,
    DirectDebitData,
    PendingTransactionData,
    ProviderConnectionContext,
    StandingOrderData,
    TransactionData,
)


class BaseProvider(ABC):
    provider_type: str
    auth: BaseProviderAuth
    supports_pending: bool = False
    supports_direct_debits: bool = False
    supports_cards: bool = False
    supports_standing_orders: bool = False

    def __init__(self) -> None:
        if not hasattr(self, "auth"):
            raise RuntimeError("Provider auth not configured")

    async def get_auth_url(self, context: ProviderConnectionContext) -> str | None:
        return await self.auth.get_auth_url(context)

    async def exchange_code(
        self, context: ProviderConnectionContext, code: str, state: str | None = None
    ) -> dict:
        return await self.auth.exchange_code(context, code=code, state=state)

    async def refresh_if_needed(self, context: ProviderConnectionContext) -> dict:
        return await self.auth.refresh_if_needed(context)

    async def is_connection_valid(self, context: ProviderConnectionContext) -> bool:
        return await self.auth.is_valid(context)

    @abstractmethod
    async def get_accounts(self, context: ProviderConnectionContext) -> list[AccountData]: ...

    @abstractmethod
    async def get_balances(
        self, context: ProviderConnectionContext, accounts: list[AccountData]
    ) -> list[BalanceData]: ...

    @abstractmethod
    async def get_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[TransactionData]: ...

    async def get_pending_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[PendingTransactionData]:
        return []

    async def get_cards(self, context: ProviderConnectionContext) -> list[CardData]:
        return []

    async def get_direct_debits(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[DirectDebitData]:
        return []

    async def get_standing_orders(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[StandingOrderData]:
        return []
