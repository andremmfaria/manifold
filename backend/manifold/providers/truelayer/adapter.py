from __future__ import annotations

from manifold.providers.base import BaseProvider
from manifold.providers.exceptions import ProviderAuthError
from manifold.providers.truelayer.auth import build_auth
from manifold.providers.truelayer.client import TrueLayerClient
from manifold.providers.truelayer.mappers import (
    map_account,
    map_balance,
    map_card,
    map_direct_debit,
    map_standing_order,
    map_transaction,
)
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


class TrueLayerProvider(BaseProvider):
    provider_type = "truelayer"
    supports_pending = True
    supports_direct_debits = True
    supports_cards = True
    supports_standing_orders = True

    def __init__(self) -> None:
        self.auth = build_auth()
        super().__init__()

    async def _client(
        self, context: ProviderConnectionContext
    ) -> tuple[ProviderConnectionContext, TrueLayerClient]:
        credentials = await self.refresh_if_needed(context)
        access_token = str(credentials.get("access_token") or "")
        if not access_token:
            raise ProviderAuthError()
        updated = ProviderConnectionContext(
            id=context.id,
            user_id=context.user_id,
            provider_type=context.provider_type,
            credentials=credentials,
            config=context.config,
        )
        return updated, TrueLayerClient(access_token)

    async def get_accounts(self, context: ProviderConnectionContext) -> list[AccountData]:
        _, client = await self._client(context)
        try:
            payload = await client.get("/data/v1/accounts")
            return [map_account(item) for item in payload.get("results", [])]
        finally:
            await client.aclose()

    async def get_balances(
        self, context: ProviderConnectionContext, accounts: list[AccountData]
    ) -> list[BalanceData]:
        _, client = await self._client(context)
        try:
            items: list[BalanceData] = []
            for account in accounts:
                payload = await client.get(
                    f"/data/v1/accounts/{account.provider_account_id}/balance"
                )
                for row in payload.get("results", []):
                    items.append(map_balance(account.provider_account_id, row))
            return items
        finally:
            await client.aclose()

    async def get_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[TransactionData]:
        _, client = await self._client(context)
        try:
            payload = await client.get(
                f"/data/v1/accounts/{account.provider_account_id}/transactions"
            )
            items: list[TransactionData] = []
            for item in payload.get("results", []):
                mapped = map_transaction(item)
                if isinstance(mapped, TransactionData):
                    items.append(mapped)
            return items
        finally:
            await client.aclose()

    async def get_pending_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[PendingTransactionData]:
        _, client = await self._client(context)
        try:
            payload = await client.get(
                f"/data/v1/accounts/{account.provider_account_id}/transactions/pending"
            )
            items: list[PendingTransactionData] = []
            for item in payload.get("results", []):
                mapped = map_transaction(item, pending=True)
                if isinstance(mapped, PendingTransactionData):
                    items.append(mapped)
            return items
        finally:
            await client.aclose()

    async def get_cards(self, context: ProviderConnectionContext) -> list[CardData]:
        _, client = await self._client(context)
        try:
            payload = await client.get("/data/v1/cards")
            return [map_card(item) for item in payload.get("results", [])]
        finally:
            await client.aclose()

    async def get_direct_debits(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[DirectDebitData]:
        _, client = await self._client(context)
        try:
            payload = await client.get(
                f"/data/v1/accounts/{account.provider_account_id}/direct_debits"
            )
            return [map_direct_debit(item) for item in payload.get("results", [])]
        finally:
            await client.aclose()

    async def get_standing_orders(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[StandingOrderData]:
        _, client = await self._client(context)
        try:
            payload = await client.get(
                f"/data/v1/accounts/{account.provider_account_id}/standing_orders"
            )
            return [map_standing_order(item) for item in payload.get("results", [])]
        finally:
            await client.aclose()
