from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.database import db_session
from manifold.domain.ownership import get_accessible_scope
from manifold.domain.sync_engine import SyncEngine
from manifold.models.oauth_state import OAuthState
from manifold.models.provider_connection import ProviderConnection
from manifold.models.sync_run import SyncRun
from manifold.models.user import User
from manifold.providers.registry import register_all, registry
from manifold.providers.types import ProviderConnectionContext
from manifold.schemas.connections import (
    ConnectionAuthUrlResponse,
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionSyncResponse,
    ConnectionUpdateRequest,
)
from manifold.schemas.sync_runs import SyncRunResponse
from manifold.tasks.sync import sync_connection

router = APIRouter()


def _serialize_connection(connection: ProviderConnection) -> dict:
    return {
        "id": str(connection.id),
        "user_id": str(connection.user_id),
        "provider_type": connection.provider_type,
        "display_name": connection.display_name,
        "status": connection.status,
        "auth_status": connection.auth_status,
        "config": connection.config or {},
        "consent_expires_at": connection.consent_expires_at.isoformat()
        if connection.consent_expires_at
        else None,
        "last_sync_at": connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        "created_at": connection.created_at.isoformat(),
        "updated_at": connection.updated_at.isoformat(),
    }


async def _load_connection_or_404(session: AsyncSession, connection_id: str) -> ProviderConnection:
    result = await session.execute(
        select(
            ProviderConnection.__table__.c.id,
            ProviderConnection.__table__.c.user_id,
        ).where(ProviderConnection.__table__.c.id == parse_uuid(connection_id))
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _load() -> ProviderConnection:
        connection = await session.get(ProviderConnection, parse_uuid(connection_id))
        if connection is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return connection

    return await with_user_dek(session, row.user_id, _load)


@router.get("", operation_id="listConnections", response_model=list[ConnectionResponse])
async def list_connections(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[ConnectionResponse]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(
            ProviderConnection.__table__.c.id,
            ProviderConnection.__table__.c.user_id,
        ).where(ProviderConnection.__table__.c.user_id.in_(scope_to_uuids(scope)))
    )
    items = []
    for connection_id, owner_user_id in result.all():
        async def _load() -> ProviderConnection:
            connection = await session.get(ProviderConnection, connection_id)
            if connection is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return connection

        connection = await with_user_dek(session, owner_user_id, _load)
        items.append(_serialize_connection(connection))
    return items


@router.post("", operation_id="createConnection", response_model=ConnectionResponse, status_code=201)
async def create_connection(
    payload: ConnectionCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    register_all()
    _ = registry.get(payload.provider_type)
    async def _create() -> dict:
        connection = ProviderConnection(
            user_id=current_user.id,
            provider_type=payload.provider_type,
            display_name=payload.display_name,
            status="inactive",
            auth_status="connected",
            credentials_encrypted=payload.credentials or {},
            config=payload.config or {},
        )
        session.add(connection)
        await session.commit()
        await session.refresh(connection)
        return _serialize_connection(connection)

    return await with_user_dek(session, current_user.id, _create)


@router.get("/{connection_id}", operation_id="getConnection", response_model=ConnectionResponse)
async def get_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    connection = await _load_connection_or_404(session, connection_id)
    scope = await get_accessible_scope(current_user, session)
    if str(connection.user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    async def _serialize() -> dict:
        return _serialize_connection(connection)

    return await with_user_dek(session, connection.user_id, _serialize)


@router.patch(
    "/{connection_id}",
    operation_id="updateConnection",
    response_model=ConnectionResponse,
)
async def update_connection(
    connection_id: str,
    payload: ConnectionUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionResponse:
    connection = await _load_connection_or_404(session, connection_id)
    if str(connection.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    async def _update() -> dict:
        if payload.display_name is not None:
            connection.display_name = payload.display_name
        if payload.status is not None:
            connection.status = payload.status
        if payload.auth_status is not None:
            connection.auth_status = payload.auth_status
        if payload.credentials is not None:
            connection.credentials_encrypted = payload.credentials
        if payload.config is not None:
            connection.config = payload.config
        await session.commit()
        await session.refresh(connection)
        return _serialize_connection(connection)

    return await with_user_dek(session, current_user.id, _update)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    connection = await _load_connection_or_404(session, connection_id)
    if str(connection.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    await session.delete(connection)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/{connection_id}/auth-url",
    operation_id="getConnectionAuthUrl",
    response_model=ConnectionAuthUrlResponse,
)
async def get_connection_auth_url(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionAuthUrlResponse:
    register_all()
    connection = await _load_connection_or_404(session, connection_id)
    if str(connection.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    async def _auth_url() -> ConnectionAuthUrlResponse:
        provider = registry.get(connection.provider_type)
        state = secrets.token_urlsafe(24)
        session.add(
            OAuthState(
                state=state,
                provider_type=connection.provider_type,
                connection_id=connection.id,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        config = dict(connection.config or {})
        config["oauth_state"] = state
        connection.config = config
        await session.flush()
        context = ProviderConnectionContext(
            id=str(connection.id),
            user_id=str(connection.user_id),
            provider_type=connection.provider_type,
            credentials=dict(connection.credentials_encrypted or {}),
            config=config,
        )
        auth_url = await provider.get_auth_url(context)
        await session.commit()
        return {"auth_url": auth_url}

    return await with_user_dek(session, current_user.id, _auth_url)


@router.post(
    "/{connection_id}/sync",
    operation_id="triggerConnectionSync",
    response_model=ConnectionSyncResponse,
    status_code=202,
)
async def trigger_connection_sync(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionSyncResponse:
    connection = await _load_connection_or_404(session, connection_id)
    if str(connection.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    run = SyncRun(provider_connection_id=connection.id, status="queued")
    session.add(run)
    await session.commit()
    try:
        await sync_connection.kiq(connection_id, str(run.id))
        return {"sync_run_id": str(run.id), "status": "queued"}
    except Exception:  # noqa: BLE001
        async with db_session() as sync_session:
            synced_run = await SyncEngine(sync_session).sync_connection_by_id(
                connection_id,
                str(run.id),
            )
        return {"sync_run_id": str(synced_run.id), "status": synced_run.status}


@router.get(
    "/{connection_id}/sync-runs",
    operation_id="listConnectionSyncRuns",
    response_model=list[SyncRunResponse],
)
async def list_connection_sync_runs(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SyncRunResponse]:
    connection = await _load_connection_or_404(session, connection_id)
    scope = await get_accessible_scope(current_user, session)
    if str(connection.user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    result = await session.execute(
        select(SyncRun)
        .where(SyncRun.provider_connection_id == connection.id)
        .order_by(SyncRun.created_at.desc())
    )
    return [
        {
            "id": str(item.id),
            "status": item.status,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "accounts_synced": item.accounts_synced,
            "transactions_synced": item.transactions_synced,
            "new_transactions": item.new_transactions,
            "error_code": item.error_code,
            "error_detail": item.error_detail,
            "created_at": item.created_at.isoformat(),
        }
        for item in result.scalars().all()
    ]
