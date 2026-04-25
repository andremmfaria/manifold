from __future__ import annotations

from abc import ABC
from typing import Any

from manifold.providers.types import ProviderConnectionContext


class BaseProviderAuth(ABC):
    async def get_auth_url(self, _context: ProviderConnectionContext) -> str | None:
        return None

    async def exchange_code(
        self,
        _context: ProviderConnectionContext,
        *,
        code: str,
        state: str | None = None,
    ) -> dict[str, Any]:
        return {"code": code, "state": state}

    async def prepare_request_headers(self, context: ProviderConnectionContext) -> dict[str, str]:
        return {}

    async def refresh_if_needed(self, context: ProviderConnectionContext) -> dict[str, Any]:
        return context.credentials

    async def is_valid(self, _context: ProviderConnectionContext) -> bool:
        return True
