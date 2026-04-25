from __future__ import annotations

from manifold.providers.auth import ApiKeyAuth, BasicAuth, BearerTokenAuth, NoAuth
from manifold.providers.auth.base import BaseProviderAuth


def build_auth(mode: str | None) -> BaseProviderAuth:
    normalized = (mode or "none").lower()
    if normalized == "api_key":
        return ApiKeyAuth()
    if normalized == "bearer":
        return BearerTokenAuth()
    if normalized == "basic":
        return BasicAuth()
    return NoAuth()
