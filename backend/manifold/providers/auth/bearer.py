from __future__ import annotations

from manifold.providers.auth.base import BaseProviderAuth
from manifold.providers.types import ProviderConnectionContext


class BearerTokenAuth(BaseProviderAuth):
    async def prepare_request_headers(self, context: ProviderConnectionContext) -> dict[str, str]:
        token = str(
            context.credentials.get("access_token") or context.config.get("access_token") or ""
        )
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def is_valid(self, context: ProviderConnectionContext) -> bool:
        return bool(context.credentials.get("access_token") or context.config.get("access_token"))
