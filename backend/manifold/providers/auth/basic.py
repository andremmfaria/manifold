from __future__ import annotations

import base64

from manifold.providers.auth.base import BaseProviderAuth
from manifold.providers.types import ProviderConnectionContext


class BasicAuth(BaseProviderAuth):
    async def prepare_request_headers(self, context: ProviderConnectionContext) -> dict[str, str]:
        username = str(context.credentials.get("username") or context.config.get("username") or "")
        password = str(context.credentials.get("password") or context.config.get("password") or "")
        if not username:
            return {}
        raw = base64.b64encode(f"{username}:{password}".encode()).decode("utf-8")
        return {"Authorization": f"Basic {raw}"}

    async def is_valid(self, context: ProviderConnectionContext) -> bool:
        return bool(context.credentials.get("username") or context.config.get("username"))
