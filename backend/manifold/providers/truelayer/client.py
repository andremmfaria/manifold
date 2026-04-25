from __future__ import annotations

import asyncio

import httpx

from manifold.config import settings
from manifold.providers.exceptions import ProviderRateLimitError, SyncError


class TrueLayerClient:
    def __init__(self, access_token: str) -> None:
        base_url = (
            "https://api.truelayer-sandbox.com"
            if settings.truelayer_sandbox
            else "https://api.truelayer.com"
        )
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def get(self, path: str) -> dict:
        delay = 1
        for _ in range(3):
            response = await self._client.get(path)
            if response.status_code == 429:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if response.status_code >= 400:
                raise SyncError(
                    "TrueLayer request failed",
                    detail={"status_code": response.status_code, "path": path},
                )
            return response.json()
        raise ProviderRateLimitError(detail={"path": path})

    async def aclose(self) -> None:
        await self._client.aclose()
