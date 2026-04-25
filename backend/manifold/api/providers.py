from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.models.oauth_state import OAuthState
from manifold.models.provider_connection import ProviderConnection
from manifold.models.user import User
from manifold.providers.registry import register_all, registry
from manifold.providers.types import ProviderConnectionContext
from manifold.schemas.providers import ProviderTypeResponse

router = APIRouter()


@router.get("", response_model=list[ProviderTypeResponse])
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> list[ProviderTypeResponse]:
    del current_user
    register_all()
    items = []
    for provider_type in registry.list_types():
        provider = registry.get(provider_type)
        items.append(
            ProviderTypeResponse(
                type=provider.provider_type,
                supports_pending=provider.supports_pending,
                supports_direct_debits=provider.supports_direct_debits,
                supports_cards=provider.supports_cards,
                supports_standing_orders=provider.supports_standing_orders,
            )
        )
    return items


@router.get("/{provider_type}/callback")
async def provider_callback(
    provider_type: str,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    register_all()
    provider = registry.get(provider_type)
    result = await session.execute(select(OAuthState).where(OAuthState.state == state))
    oauth_state = result.scalar_one_or_none()
    if oauth_state is None or oauth_state.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=400, detail={"error": "invalid_state"})

    owner_result = await session.execute(
        select(ProviderConnection.__table__.c.user_id).where(
            ProviderConnection.__table__.c.id == parse_uuid(oauth_state.connection_id)
        )
    )
    owner_user_id = owner_result.scalar_one_or_none()
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _callback() -> dict[str, str]:
        connection = await session.get(ProviderConnection, parse_uuid(oauth_state.connection_id))
        if connection is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        context = ProviderConnectionContext(
            id=str(connection.id),
            user_id=str(connection.user_id),
            provider_type=connection.provider_type,
            credentials=dict(connection.credentials_encrypted or {}),
            config=dict(connection.config or {}),
        )
        token_payload = await provider.exchange_code(context, code, state)
        connection.credentials_encrypted = token_payload
        if token_payload.get("expires_at"):
            connection.consent_expires_at = datetime.fromisoformat(
                str(token_payload["expires_at"]).replace("Z", "+00:00")
            )
        connection.status = "active"
        connection.auth_status = "connected"
        await session.delete(oauth_state)
        await session.commit()
        return {
            "status": "connected",
            "redirect": "/connections/" + str(connection.id) + "?" + urlencode({"connected": "1"}),
        }

    return await with_user_dek(session, owner_user_id, _callback)
