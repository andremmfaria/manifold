from __future__ import annotations

from manifold.providers.auth.base import BaseProviderAuth
from manifold.providers.types import ProviderConnectionContext


class ApiKeyAuth(BaseProviderAuth):
    def __init__(self, header_name: str = "x-api-key") -> None:
        self.header_name = header_name

    async def prepare_request_headers(self, context: ProviderConnectionContext) -> dict[str, str]:
        token = str(context.credentials.get("api_key") or context.config.get("api_key") or "")
        return {self.header_name: token} if token else {}

    async def is_valid(self, context: ProviderConnectionContext) -> bool:
        return bool(context.credentials.get("api_key") or context.config.get("api_key"))
