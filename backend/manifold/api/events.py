from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.event import Event
from manifold.models.provider_connection import ProviderConnection
from manifold.models.sync_run import SyncRun
from manifold.models.user import User

router = APIRouter()


@router.get("/sync-runs")
async def list_sync_runs(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(SyncRun, ProviderConnection.__table__.c.user_id)
        .join(
            ProviderConnection.__table__,
            SyncRun.provider_connection_id == ProviderConnection.__table__.c.id,
        )
        .where(ProviderConnection.__table__.c.user_id.in_(scope_to_uuids(scope)))
    )
    return [
        {
            "id": str(run.id),
            "provider_connection_id": str(run.provider_connection_id),
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "accounts_synced": run.accounts_synced,
            "transactions_synced": run.transactions_synced,
            "new_transactions": run.new_transactions,
            "error_code": run.error_code,
            "error_detail": run.error_detail,
            "created_at": run.created_at.isoformat(),
        }
        for run, _owner_user_id in result.all()
    ]


@router.get("/sync-runs/{sync_run_id}")
async def get_sync_run(
    sync_run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(SyncRun, ProviderConnection.__table__.c.user_id)
        .join(
            ProviderConnection.__table__,
            SyncRun.provider_connection_id == ProviderConnection.__table__.c.id,
        )
        .where(SyncRun.id == sync_run_id)
    )
    row = result.one_or_none()
    if row is None or str(row[1]) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    run = row[0]
    return {
        "id": str(run.id),
        "provider_connection_id": str(run.provider_connection_id),
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "accounts_synced": run.accounts_synced,
        "transactions_synced": run.transactions_synced,
        "new_transactions": run.new_transactions,
        "error_code": run.error_code,
        "error_detail": run.error_detail,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/events")
async def list_events(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(Event.__table__.c.id, Event.__table__.c.user_id)
        .where(Event.__table__.c.user_id.in_(scope_to_uuids(scope)))
        .order_by(Event.__table__.c.recorded_at.desc())
    )
    items: list[dict] = []
    for event_id, owner_user_id in result.all():
        async def _serialize() -> dict:
            item = await session.get(Event, event_id)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return {
                "id": str(item.id),
                "event_type": item.event_type,
                "source_type": item.source_type,
                "confidence": float(item.confidence) if item.confidence is not None else None,
                "account_id": str(item.account_id) if item.account_id else None,
                "user_id": str(item.user_id),
                "payload": item.payload,
                "occurred_at": item.occurred_at.isoformat(),
                "recorded_at": item.recorded_at.isoformat(),
                "explanation": item.explanation,
            }

        items.append(await with_user_dek(session, owner_user_id, _serialize))
    return items


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(Event.__table__.c.user_id).where(Event.__table__.c.id == parse_uuid(event_id))
    )
    owner_user_id = result.scalar_one_or_none()
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    scope = await get_accessible_scope(current_user, session)
    if str(owner_user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _get() -> dict:
        item = await session.get(Event, parse_uuid(event_id))
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return {
            "id": str(item.id),
            "event_type": item.event_type,
            "source_type": item.source_type,
            "confidence": float(item.confidence) if item.confidence is not None else None,
            "account_id": str(item.account_id) if item.account_id else None,
            "user_id": str(item.user_id),
            "payload": item.payload,
            "occurred_at": item.occurred_at.isoformat(),
            "recorded_at": item.recorded_at.isoformat(),
            "explanation": item.explanation,
        }

    return await with_user_dek(session, owner_user_id, _get)
