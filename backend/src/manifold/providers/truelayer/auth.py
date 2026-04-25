from __future__ import annotations

from manifold.config import settings
from manifold.providers.auth.oauth2 import OAuth2CodeFlowAuth


def build_auth() -> OAuth2CodeFlowAuth:
    auth_host = (
        "https://auth.truelayer-sandbox.com"
        if settings.truelayer_sandbox
        else "https://auth.truelayer.com"
    )
    return OAuth2CodeFlowAuth(
        client_id=settings.truelayer_client_id,
        client_secret=settings.truelayer_client_secret,
        redirect_uri=settings.truelayer_redirect_uri,
        authorize_url=f"{auth_host}/",
        token_url=f"{auth_host}/connect/token",
        scopes=[
            "accounts",
            "balance",
            "transactions",
            "direct_debits",
            "standing_orders",
            "offline_access",
        ],
    )
