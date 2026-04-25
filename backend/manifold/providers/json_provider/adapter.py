from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import httpx

from manifold.providers.base import BaseProvider
from manifold.providers.exceptions import SyncError
from manifold.providers.json_provider.auth import build_auth
from manifold.providers.json_provider.mappers import map_account, map_balance, map_transaction
from manifold.providers.types import (
    AccountData,
    BalanceData,
    ProviderConnectionContext,
    TransactionData,
)


class JsonProvider(BaseProvider):
    provider_type = "json"

    def __init__(self) -> None:
        self.auth = build_auth(None)
        super().__init__()

    def _mapping(self, context: ProviderConnectionContext) -> dict:
        return dict(context.config.get("mapping") or {})

    async def _fetch_payload(self, context: ProviderConnectionContext) -> dict:
        self.auth = build_auth(str(context.config.get("auth_mode") or "none"))
        source = str(context.config.get("url") or context.config.get("path") or "")
        if not source:
            raise SyncError("JSON provider source missing", error_code="validation_error")
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            headers = await self.auth.prepare_request_headers(context)
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(source, headers=headers)
            if response.status_code >= 400:
                raise SyncError(
                    "JSON provider fetch failed", detail={"status_code": response.status_code}
                )
            payload = response.json()
        else:
            path = Path(source)
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                raise SyncError("JSON fixture path missing", error_code="validation_error")
            payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SyncError("JSON provider payload invalid", error_code="validation_error")
        return payload

    async def get_accounts(self, context: ProviderConnectionContext) -> list[AccountData]:
        payload = await self._fetch_payload(context)
        mapping = self._mapping(context)
        accounts = payload.get(str(mapping.get("accounts_path") or "accounts"), [])
        if not isinstance(accounts, list):
            raise SyncError("accounts payload invalid", error_code="validation_error")
        return [map_account(item, mapping) for item in accounts if isinstance(item, dict)]

    async def get_balances(
        self, context: ProviderConnectionContext, accounts: list[AccountData]
    ) -> list[BalanceData]:
        payload = await self._fetch_payload(context)
        mapping = self._mapping(context)
        balances_key = str(mapping.get("balances_path") or "balances")
        if isinstance(payload.get(balances_key), list):
            return [
                map_balance(item, mapping)
                for item in payload[balances_key]
                if isinstance(item, dict)
            ]
        return [
            map_balance(
                {
                    "id": account.provider_account_id,
                    "balance": payload.get("account_balances", {}).get(account.provider_account_id),
                    "currency": account.currency,
                },
                mapping,
            )
            for account in accounts
            if payload.get("account_balances", {}).get(account.provider_account_id) is not None
        ]

    async def get_transactions(
        self, context: ProviderConnectionContext, account: AccountData
    ) -> list[TransactionData]:
        payload = await self._fetch_payload(context)
        mapping = self._mapping(context)
        transactions = payload.get(str(mapping.get("transactions_path") or "transactions"), [])
        if not isinstance(transactions, list):
            raise SyncError("transactions payload invalid", error_code="validation_error")
        result: list[TransactionData] = []
        for item in transactions:
            if not isinstance(item, dict):
                continue
            account_key = str(mapping.get("transaction_account_id", "account_id"))
            if str(item.get(account_key)) != account.provider_account_id:
                continue
            result.append(map_transaction(item, mapping))
        return result
