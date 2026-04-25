from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from manifold.providers.auth.base import BaseProviderAuth
from manifold.providers.exceptions import ProviderAuthError
from manifold.providers.types import ProviderConnectionContext


class OAuth2CodeFlowAuth(BaseProviderAuth):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        authorize_url: str,
        token_url: str,
        scopes: list[str],
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.scopes = scopes

    async def get_auth_url(self, context: ProviderConnectionContext) -> str:
        state = str(context.config.get("oauth_state") or "")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": " ".join(self.scopes),
                "state": state,
            }
        )
        return f"{self.authorize_url}?{query}"

    async def exchange_code(
        self, context: ProviderConnectionContext, *, code: str, state: str | None = None
    ) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "code": code,
                    "state": state or context.config.get("oauth_state"),
                },
            )
        if response.status_code >= 400:
            raise ProviderAuthError(detail={"status_code": response.status_code})
        payload = response.json()
        return self._with_expiry(payload)

    async def refresh_if_needed(self, context: ProviderConnectionContext) -> dict:
        credentials = dict(context.credentials)
        expires_at = credentials.get("expires_at")
        if not expires_at:
            return credentials
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expires_dt - datetime.now(UTC) > timedelta(minutes=5):
            return credentials
        refresh_token = credentials.get("refresh_token")
        if not refresh_token:
            raise ProviderAuthError("refresh token missing")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                },
            )
        if response.status_code >= 400:
            raise ProviderAuthError(detail={"status_code": response.status_code})
        payload = response.json()
        if "refresh_token" not in payload:
            payload["refresh_token"] = refresh_token
        return self._with_expiry(payload)

    async def prepare_request_headers(self, context: ProviderConnectionContext) -> dict[str, str]:
        token = str(context.credentials.get("access_token") or "")
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def is_valid(self, context: ProviderConnectionContext) -> bool:
        return bool(
            context.credentials.get("access_token") or context.credentials.get("refresh_token")
        )

    @staticmethod
    def _with_expiry(payload: dict) -> dict:
        expires_in = int(payload.get("expires_in") or 3600)
        payload["expires_at"] = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()
        return payload
